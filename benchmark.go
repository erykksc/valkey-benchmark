package main

import (
	"context"
	"encoding/binary"
	"encoding/csv"
	"errors"
	"flag"
	"fmt"
	"math/rand/v2"
	"os"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/valkey-io/valkey-go"
)

const (
	SEED1 uint64 = 1
	SEED2 uint64 = 2
)

type DataPool struct {
	buffer []byte
	size   int
}

func NewDataPool(rng *rand.ChaCha8, size int) *DataPool {
	b := make([]byte, size)
	_, err := rng.Read(b)
	if err != nil {
		panic("Error generating random data for the new DataPool")
	}
	return &DataPool{buffer: b, size: size}
}

func (p *DataPool) GetRandomSlice(rng *rand.Rand, length int) ([]byte, error) {
	if length <= 0 {
		return nil, errors.New("requesting slice of size smaller or equal to 0")
	}
	if length > p.size {
		return nil, errors.New("requesting slice of size larger than DataPoolSize")
	}
	maxOffset := p.size - length
	offset := rng.IntN(maxOffset + 1)
	return p.buffer[offset : offset+length], nil
}

type OperationResult struct {
	OperationType string
	KeyID         uint64
	FinishedAt    time.Time
	Latency       time.Duration
	Success       bool
}

func main() {
	targetAddr := flag.String("target-addr", "127.0.0.1:6379", "Address of the Valkey instance or a comma separated list of initial cluster nodes")
	password := flag.String("password", "", "Password to use for authentication with valkey-server")
	totalKeys := flag.Uint64("total-keys", 1000000, "Total key amount")
	concurrency := flag.Int("concurrency", 1024, "Number of simultaneous workers")
	poolSizeMB := flag.Int("pool-size", 100, "Data Pool size of random data in MB")
	duration := flag.Duration("duration", 20*time.Minute, "Duration of the benchmark")
	flag.Parse()

	poolSize := *poolSizeMB * 1024 * 1024

	addrs := strings.Split(*targetAddr, ",")
	client, err := valkey.NewClient(valkey.ClientOption{
		InitAddress: addrs,
		Password:    *password,
	})
	if err != nil {
		panic(fmt.Errorf("error connecting to Valkey: %w", err))
	}
	defer client.Close()

	// Get cluster size and server info after connecting
	var clusterSize int
	var serverInfoString string
	info, err := client.Do(context.Background(), client.B().Arbitrary("CLUSTER", "INFO").Build()).ToString()
	if err != nil {
		if strings.Contains(err.Error(), "This instance has cluster support disabled") {
			clusterSize = 1
			// It's a standalone server, get regular INFO
			standaloneInfo, infoErr := client.Do(context.Background(), client.B().Info().Build()).ToString()
			if infoErr != nil {
				panic(fmt.Errorf("failed to get standalone server info: %w", infoErr))
			}
			serverInfoString = standaloneInfo
		} else {
			panic(fmt.Errorf("failed to get cluster info: %w", err))
		}
	} else {
		serverInfoString = info // It's a cluster, we already have the info
		// Parse the info string to find cluster_size, using CutPrefix
		for line := range strings.SplitSeq(info, "\r\n") {
			if sizeStr, found := strings.CutPrefix(line, "cluster_size:"); found {
				size, parseErr := strconv.Atoi(sizeStr)
				if parseErr != nil {
					panic(fmt.Errorf("failed to parse cluster_size '%s': %w", sizeStr, parseErr))
				}
				clusterSize = size
				break
			}
		}
		if clusterSize == 0 {
			// Fallback for safety, e.g. if CLUSTER INFO command changes in a future Valkey version
			clusterSize = len(addrs)
		}
	}

	// setup data pool
	var seed [32]byte
	binary.LittleEndian.PutUint64(seed[0:], SEED1)
	binary.LittleEndian.PutUint64(seed[8:], SEED2)
	rng := rand.NewChaCha8(seed)
	pool := NewDataPool(rng, poolSize)

	// setup zipf distribution for keys to simulate hot keys
	z := rand.NewZipf(rand.New(rand.NewPCG(SEED1, SEED2)), 1.1, 1.0, *totalKeys)

	benchmarkStartTime := time.Now()
	benchmarkRunID := benchmarkStartTime.Format("20060102-150405") // Unique ID for this run

	err = os.MkdirAll("results", 0755)
	if err != nil {
		panic("Couldn't create a 'results' directory")
	}
	outputFile := fmt.Sprintf("results/results_%s_nodes-%d_conc-%d_keys-%d_dur-%ds.csv",
		benchmarkRunID,
		clusterSize,
		*concurrency,
		*totalKeys,
		int(duration.Seconds()),
	)

	resultsQueue := make(chan OperationResult, *concurrency*100)
	var resultsWg sync.WaitGroup

	resultsWg.Go(
		func() {
			file, err := os.Create(outputFile)
			if err != nil {
				panic(fmt.Sprintf("Failed to create output file '%s': %v", outputFile, err))
			}
			defer file.Close()

			fmt.Fprintf(file, "# Benchmark Configuration for Run ID: %s\n", benchmarkRunID)
			fmt.Fprintf(file, "#   Target Address: %s\n", *targetAddr)
			fmt.Fprintf(file, "#   Total Keys: %d\n", *totalKeys)
			fmt.Fprintf(file, "#   Concurrency: %d\n", *concurrency)
			fmt.Fprintf(file, "#   Data Pool Size (MB): %d\n", *poolSizeMB)
			fmt.Fprintf(file, "#   Duration: %s\n", duration)
			fmt.Fprintf(file, "#   Benchmark Start Time: %s\n", benchmarkStartTime.Format(time.RFC3339))
			fmt.Fprintf(file, "#   Go Version: %s\n", runtime.Version())
			fmt.Fprintf(file, "#   GOMAXPROCS: %d\n", runtime.GOMAXPROCS(0))
			fmt.Fprintf(file, "#   OS/Arch: %s/%s\n", runtime.GOOS, runtime.GOARCH)
			fmt.Fprintf(file, "#   Output File: %s\n", outputFile) // Include generated filename
			fmt.Fprintf(file, "#\n# Server / Cluster Info:\n# ------------------------\n")
			commentedInfo := "# " + strings.ReplaceAll(strings.TrimSpace(serverInfoString), "\r\n", "\n# ")
			fmt.Fprintf(file, "%s\n", commentedInfo)
			fmt.Fprintf(file, "#-------------------------------------------------\n")

			writer := csv.NewWriter(file)
			defer writer.Flush()

			header := []string{"FinishedAt", "OperationType", "KeyID", "Latency(us)", "Success"}
			if err := writer.Write(header); err != nil {
				panic(fmt.Sprintf("Failed to write CSV header: %v", err))
			}

			var opsCount uint64
			for result := range resultsQueue {
				opsCount++
				record := []string{
					strconv.FormatInt(result.FinishedAt.Unix(), 10),
					result.OperationType,
					strconv.FormatUint(result.KeyID, 10),
					strconv.FormatInt(result.Latency.Microseconds(), 10),
					strconv.FormatBool(result.Success),
				}
				if err := writer.Write(record); err != nil {
					panic(fmt.Sprintf("Error writing record to CSV: %v\n", err))
				}
			}
			fmt.Printf("\n[Processor] Finished writing %d results to %s\n", opsCount, outputFile)
		})

	ctx := context.Background()
	var workersWg sync.WaitGroup

	fmt.Printf("Benchmark started (Run ID: %s): %d workers for %v\n", benchmarkRunID, *concurrency, duration)
	fmt.Printf("Target: %s | Keys: %d | Pool: %dMB | Output: %s\n", *targetAddr, *totalKeys, *poolSizeMB, outputFile)

	for i := 0; i < *concurrency; i++ {
		workersWg.Go(func() {
			// each worker gets its own data generator for data
			rng := rand.New(rand.NewPCG(SEED1, uint64(i)))
			for {
				elapsed := time.Since(benchmarkStartTime)
				if elapsed >= *duration {
					return
				}

				// Linear probability shift from write-heavy to read-heavy.
				progress := elapsed.Seconds() / duration.Seconds()
				getProb := 0.1 + (progress * 0.8)

				keyID := z.Uint64()
				key := "prefix:" + fmt.Sprintf("%016d", keyID)

				var opType string
				var opErr error

				startOp := time.Now()
				if rng.Float64() < getProb {
					// Perform a GET operation.
					opType = "GET"
					opErr = client.Do(ctx, client.B().Get().Key(key).Build()).Error()
				} else {
					// Perform a SET operation.
					opType = "SET"
					var valSize int
					// Bimodal distribution for value sizes.
					const KiB = 1024
					valSize = int(rng.NormFloat64()*(0.75*KiB) + (1.5 * KiB))
					valSize = max(2, valSize)         // Minimal byte size, 2 because of an empty JSON '{}'
					valSize = min(pool.size, valSize) // Maximal byte size

					val, err := pool.GetRandomSlice(rng, valSize)
					if err != nil {
						panic(err.Error())
					}
					opErr = client.Do(ctx, client.B().Set().Key(key).Value(valkey.BinaryString(val)).Build()).Error()
				}
				finishedAt := time.Now()
				latency := finishedAt.Sub(startOp)

				resultsQueue <- OperationResult{
					FinishedAt:    finishedAt,
					OperationType: opType,
					KeyID:         keyID,
					Latency:       latency,
					Success:       opErr == nil,
				}
			}
		})
	}

	// progress tracker
	stopReporter := make(chan bool)
	go func() {
		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				fmt.Printf("[%v] Benchmark in progress (Run ID: %s)\n", time.Since(benchmarkStartTime).Round(time.Second), benchmarkRunID)
			case <-stopReporter:
				return
			}
		}
	}()

	workersWg.Wait()
	close(stopReporter)
	close(resultsQueue)
	resultsWg.Wait()

	fmt.Println("\n--- Benchmark Finished ---")
	fmt.Printf("Total duration for Run ID %s: %v\n", benchmarkRunID, time.Since(benchmarkStartTime).Round(time.Second))
}
