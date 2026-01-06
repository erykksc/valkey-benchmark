package main

import (
	"context"
	crand "crypto/rand"
	"encoding/csv"
	"errors"
	"flag"
	"fmt"
	"math/rand/v2"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/valkey-io/valkey-go"
)

type DataPool struct {
	buffer []byte
	size   int
}

func NewDataPool(size int) *DataPool {
	b := make([]byte, size)
	_, err := crand.Read(b)
	if err != nil {
		panic("Error generating random data for the new DataPool")
	}
	return &DataPool{buffer: b, size: size}
}

func (p *DataPool) GetRandomSlice(length int) ([]byte, error) {
	if length <= 0 {
		return nil, errors.New("requesting slice of size smaller or equal to 0")
	}
	if length > p.size {
		return nil, errors.New("requesting slice of size larger than DataPoolSize")
	}
	maxOffset := p.size - length
	offset := rand.IntN(maxOffset + 1)
	return p.buffer[offset : offset+length], nil
}

type OperationResult struct {
	OperationType string
	Latency       time.Duration
	Success       bool
}

func main() {
	targetAddr := flag.String("target-addr", "127.0.0.1:6379", "Address of the Valkey instance or a comma separated list of initial cluster nodes")
	totalKeys := flag.Uint64("total-keys", 1000000, "Total key amount")
	concurrency := flag.Int("concurrency", 128, "Number of simultaneous workers")
	poolSizeMB := flag.Int("pool-size", 100, "Data Pool size of random data in MB")
	duration := flag.Duration("duration", 10*time.Minute, "Duration of the benchmark")
	flag.Parse()

	poolSize := *poolSizeMB * 1024 * 1024
	client, err := valkey.NewClient(valkey.ClientOption{InitAddress: []string{*targetAddr}})
	if err != nil {
		panic(err)
	}
	defer client.Close()

	pool := NewDataPool(poolSize)
	z := rand.NewZipf(rand.New(rand.NewPCG(1, 2)), 1.1, 1.0, *totalKeys)

	startTime := time.Now()
	benchmarkRunID := startTime.Format("20060102-150405") // Unique ID for this run

	err = os.MkdirAll("results", 0755)
	if err != nil {
		panic("Couldn't create a 'results' directory")
	}
	outputFile := fmt.Sprintf("results/results_%s_conc-%d_keys-%d_dur-%ds.csv",
		benchmarkRunID,
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
			fmt.Fprintf(file, "#   Benchmark Start Time: %s\n", startTime.Format(time.RFC3339))
			fmt.Fprintf(file, "#   Output File: %s\n", outputFile) // Include generated filename
			fmt.Fprintf(file, "#-------------------------------------------------\n")

			writer := csv.NewWriter(file)
			defer writer.Flush()

			header := []string{"OperationType", "Latency(us)", "Success"}
			if err := writer.Write(header); err != nil {
				panic(fmt.Sprintf("Failed to write CSV header: %v", err))
			}

			var opsCount uint64
			for result := range resultsQueue {
				opsCount++
				record := []string{
					result.OperationType,
					strconv.FormatInt(result.Latency.Microseconds(), 10),
					strconv.FormatBool(result.Success),
				}
				if err := writer.Write(record); err != nil {
					fmt.Printf("Error writing record to CSV: %v\n", err)
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
			for {
				elapsed := time.Since(startTime)
				if elapsed >= *duration {
					return
				}

				// Linear probability shift from write-heavy to read-heavy.
				progress := elapsed.Seconds() / duration.Seconds() // Use duration
				getProb := 0.1 + (progress * 0.8)

				key := "prefix:" + fmt.Sprintf("%016d", z.Uint64())

				var opType string
				var opErr error

				startOp := time.Now()
				if rand.Float64() < getProb {
					// Perform a GET operation.
					opType = "GET"
					opErr = client.Do(ctx, client.B().Get().Key(key).Build()).Error()
				} else {
					// Perform a SET operation.
					opType = "SET"
					var valSize int
					// Bimodal distribution for value sizes.
					if rand.Float64() < 0.8 {
						valSize = int(rand.NormFloat64()*50 + 256) // Smaller values
					} else {
						valSize = int(rand.NormFloat64()*2048 + 10240) // Larger values
					}

					valSize = max(2, valSize)         // Minimal byte size
					valSize = min(pool.size, valSize) // Maximal byte size

					val, err := pool.GetRandomSlice(valSize)
					if err != nil {
						panic(err.Error())
					}
					opErr = client.Do(ctx, client.B().Set().Key(key).Value(valkey.BinaryString(val)).Build()).Error()
				}
				latency := time.Since(startOp)

				resultsQueue <- OperationResult{
					OperationType: opType,
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
				fmt.Printf("[%v] Benchmark in progress (Run ID: %s)\n", time.Since(startTime).Round(time.Second), benchmarkRunID)
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
	fmt.Printf("Total duration for Run ID %s: %v\n", benchmarkRunID, time.Since(startTime).Round(time.Second))
}
