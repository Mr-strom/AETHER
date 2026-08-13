#!/usr/bin/env python
"""Quick API integration test for AETHER FastAPI backend.

Starts uvicorn, fires test requests against the API, prints results.

Usage:
    python test_api.py
"""

import asyncio
import sys
import time
from pathlib import Path

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).parent / "backend"))


async def main():
    import httpx

    BASE = "http://127.0.0.1:8000"
    print("=" * 60)
    print("AETHER — API Integration Test")
    print("=" * 60)

    # Start uvicorn in background
    import uvicorn
    from backend.app.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)

    # Run server in background task
    server_task = asyncio.create_task(server.serve())

    # Wait for server to start
    print("\nStarting server...")
    for _ in range(30):
        await asyncio.sleep(0.5)
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{BASE}/api/health", timeout=2.0)
                if r.status_code == 200:
                    break
        except Exception:
            continue
    else:
        print("   Server failed to start in 15s")
        server.should_exit = True
        return

    print("   Server ready!")

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Test 1: Health
        print("\n" + "-" * 60)
        print("TEST 1: GET /api/health")
        r = await client.get(f"{BASE}/api/health")
        print(f"   Status: {r.status_code}")
        print(f"   Body:   {r.json()}")

        # Test 2: List Sources
        print("\n" + "-" * 60)
        print("TEST 2: GET /api/sources")
        r = await client.get(f"{BASE}/api/sources")
        data = r.json()
        print(f"   Status: {r.status_code}")
        print(f"   Total:  {data.get('total', 0)} sources")
        for s in data.get("sources", [])[:3]:
            print(f"      [{s['id']}] {s['filename']} ({s['status']})")

        # Test 3: List Evidence
        print("\n" + "-" * 60)
        print("TEST 3: GET /api/evidence")
        r = await client.get(f"{BASE}/api/evidence?limit=5")
        if r.status_code == 200:
            evidence = r.json()
            print(f"   Status: {r.status_code}")
            print(f"   Count:  {len(evidence)} chunks")
            for e in evidence[:3]:
                print(f"      [EID-{e['id']}] {e['content'][:60]}...")
        else:
            print(f"   Status: {r.status_code} — {r.text[:100]}")

        # Test 4: Query
        print("\n" + "-" * 60)
        print("TEST 4: POST /api/query")
        query = "What is the voltage reading for Panel A-001?"
        print(f"   Query: {query}")
        t0 = time.time()
        r = await client.post(f"{BASE}/api/query", json={"query": query})
        elapsed = (time.time() - t0) * 1000
        if r.status_code == 200:
            data = r.json()
            print(f"   Status:     {r.status_code}")
            print(f"   Answer:     {data['answer'][:150]}...")
            print(f"   Citations:  {data['citations']}")
            print(f"   Confidence: {data['confidence']}")
            print(f"   Evidence:   {len(data['evidence'])} pieces")
            print(f"   Latency:    {data['latency_ms']}ms (actual: {elapsed:.0f}ms)")
        else:
            print(f"   Status: {r.status_code}")
            print(f"   Error:  {r.text[:200]}")

        # Test 5: Airgap Verification
        print("\n" + "-" * 60)
        print("TEST 5: GET /api/system/verify-airgap")
        r = await client.get(f"{BASE}/api/system/verify-airgap")
        if r.status_code == 200:
            data = r.json()
            print(f"   Status:           {r.status_code}")
            ag = "🔒" if data["all_green"] else "🔓"
            sv = "✅" if data["signature_valid"] else "❌"
            ni = "✅" if data["network_isolated"] else "❌"
            print(f"   {sv} Signature valid:  {data['signature_valid']}")
            print(f"   {ni} Network isolated: {data['network_isolated']}")
            print(f"   {ag} All green:        {data['all_green']}")
        else:
            print(f"   Status: {r.status_code} — {r.text[:100]}")

    print("\n" + "=" * 60)
    print("API TEST COMPLETE")
    print("=" * 60)

    # Shutdown server
    server.should_exit = True
    await server_task


if __name__ == "__main__":
    asyncio.run(main())
