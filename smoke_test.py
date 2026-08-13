import time
import psutil
from llama_cpp import Llama
from sentence_transformers import SentenceTransformer

models_dir = "./models"
process = psutil.Process()

def get_ram():
    return process.memory_info().rss / 1024**3

print("=" * 60)
print("AETHER SMOKE TEST — Loading models one at a time")
print("=" * 60)
print(f"Available RAM at start: {get_ram():.2f} GB used")
print()

# ========== TEST 1: Granite (Planner) ==========
print("[1/3] Loading Granite 4 Tiny H (Planner + Validator)...")
ram_before = get_ram()
start = time.time()

granite = Llama(
    model_path=f"{models_dir}/granite-4.0-h-tiny-Q4_K_M.gguf",
    n_ctx=4096,
    n_threads=16,
    verbose=False
)

ram_after = get_ram()
print(f"   Loaded in {time.time()-start:.1f}s")
print(f"   RAM used: {ram_after:.2f} GB (+{ram_after-ram_before:.2f} GB)")

# Quick inference test
print("   Running inference test...")
start = time.time()
response = granite.create_chat_completion(
    messages=[{"role": "user", "content": "Say exactly: test passed"}],
    max_tokens=10,
    temperature=0.1
)
infer_time = time.time() - start
output = response["choices"][0]["message"]["content"].strip()
print(f"   Output: '{output}'")
print(f"   Inference: {infer_time:.1f}s")
print(f"   ✅ Granite PASS" if "passed" in output.lower() else f"   ❌ Granite FAIL")
print()

# ========== TEST 2: Qwen2.5-3B (Synthesizer) ==========
print("[2/3] Loading Qwen2.5-3B (Synthesizer)...")
print("   (Granite stays loaded — simulating peak RAM)")

ram_before = get_ram()
start = time.time()

qwen = Llama(
    model_path=f"{models_dir}/Qwen2.5-3B-Instruct-Q4_K_M.gguf",
    n_ctx=8192,
    n_threads=16,
    verbose=False
)

ram_after = get_ram()
print(f"   Loaded in {time.time()-start:.1f}s")
print(f"   RAM used: {ram_after:.2f} GB (+{ram_after-ram_before:.2f} GB)")

# Quick inference test
print("   Running inference test...")
start = time.time()
response = qwen.create_chat_completion(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say exactly: synthesizer works"}
    ],
    max_tokens=10,
    temperature=0.1
)
infer_time = time.time() - start
output = response["choices"][0]["message"]["content"].strip()
print(f"   Output: '{output}'")
print(f"   Inference: {infer_time:.1f}s")
print(f"   ✅ Qwen PASS" if "works" in output.lower() else f"   ❌ Qwen FAIL")
print()

# ========== TEST 3: BGE-M3 ==========
print("[3/3] Loading BGE-M3 (Embeddings)...")
ram_before = get_ram()
start = time.time()

bge = SentenceTransformer('BAAI/bge-m3', trust_remote_code=True)

ram_after = get_ram()
print(f"   Loaded in {time.time()-start:.1f}s")
print(f"   RAM used: {ram_after:.2f} GB (+{ram_after-ram_before:.2f} GB)")

# Embedding test
print("   Running embedding test...")
vec = bge.encode("This is a test sentence for AETHER")
print(f"   Vector shape: {len(vec)} dimensions")
print(f"   First 5 values: {vec[:5]}")
print(f"   ✅ BGE-M3 PASS")
print()

# ========== SUMMARY ==========
print("=" * 60)
print("SMOKE TEST SUMMARY")
print("=" * 60)
total_ram = get_ram()
print(f"Total RAM used (all models loaded): {total_ram:.2f} GB")
print(f"Your available RAM: ~6.95 GB")
print()

if total_ram > 14:
    print("⚠️  WARNING: Peak RAM is very high. Smart swapping is REQUIRED.")
    print("   In production: unload Granite before loading Qwen.")
elif total_ram > 10:
    print("⚠️  CAUTION: RAM is tight but workable with smart swapping.")
else:
    print("✅ RAM usage is healthy. Smart swapping will be smooth.")

print()
print("🎉 If all 3 tests show PASS, your machine CAN run AETHER.")
print("   You are ready to build the ingestion pipeline.")