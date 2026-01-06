package main

import (
	"context"
	crand "crypto/rand"
	"flag"
	"fmt"
	"math/rand/v2"
	"strconv"
	"time"

	"github.com/valkey-io/valkey-go"
)

type DataPool struct {
	buffer []byte
	size   int
}

func NewDataPool(size int) *DataPool {
	b := make([]byte, size)
	_, err := crand.Read(b) // Fill with random bytes once at startup
	if err != nil {
		panic("Error generating random data for the new DataPool")
	}
	return &DataPool{buffer: b, size: size}
}

func (p *DataPool) GetRandomSlice(length int) []byte {
	if length > p.size {
		length = p.size
	}
	// Pick a random starting point that allows for the requested length
	maxOffset := p.size - length
	offset := rand.IntN(maxOffset + 1)
	return p.buffer[offset : offset+length]
}

func main() {
	targetAddr := flag.String("target-addr", "127.0.0.1:6379", "Address of the Valkey instance")
	totalKeys := flag.Uint64("tatal-keys", 1000000, "Total key amount")
	concurrency := flag.Int("concurrency", 128, "Number of simultaneous workers")
	poolSizeRaw := flag.Int("pool-size", 10, "Data Pool size of random data in MB")
	duration := flag.Duration("duration", 10*time.Minute, "Duration of the benchmark")
	// clusterMode := flag.Bool("cluster-mode", false, "Enable cluster mode")
	flag.Parse()

	poolSize := *poolSizeRaw * 1024 * 1024 // Convert to MB

	// Initialize Valkey-go Client
	client, err := valkey.NewClient(valkey.ClientOption{InitAddress: []string{*targetAddr}})
	if err != nil {
		panic(err)
	}
	defer client.Close()

	pool := NewDataPool(poolSize)
	z := rand.NewZipf(rand.New(rand.NewPCG(1, 2)), 1.1, 1.0, *totalKeys)

	startTime := time.Now()
	ctx := context.Background()

	fmt.Printf("Benchmark started: %d workers for %v\n", concurrency, duration)

	for i := 0; i < *concurrency; i++ {
		go func() {
			for {
				elapsed := time.Since(startTime)
				if elapsed >= *duration {
					return
				}

				// Linear probability shift: 10% GET at start -> 90% GET at end
				progress := elapsed.Seconds() / duration.Seconds()
				getProb := 0.1 + (progress * 0.8)

				key := "prefix:" + strconv.FormatUint(z.Uint64(), 10)

				if rand.Float64() < getProb {
					// GET Operation
					client.Do(ctx, client.B().Get().Key(key).Build())
				} else {
					// SET Operation
					var valSize int
					// Bimodal size
					if rand.Float64() < 0.8 {
						valSize = int(rand.NormFloat64()*50 + 256)
					} else {
						valSize = int(rand.NormFloat64()*2048 + 10240)
					}

					val := pool.GetRandomSlice(valSize)
					client.Do(ctx, client.B().Set().Key(key).Value(valkey.BinaryString(val)).Build())
				}
			}
		}()
	}

	time.Sleep(*duration)
	fmt.Println("Benchmark finished.")
}
