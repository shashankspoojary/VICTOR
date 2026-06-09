import edge_tts, asyncio
async def test():
    communicate = edge_tts.Communicate('This is a test of the Victor Text to Speech system.', 'en-US-ChristopherNeural')
    total_bytes = 0
    async for chunk in communicate.stream():
        print("Chunk type:", chunk['type'])
        if chunk['type'] == 'audio':
            total_bytes += len(chunk['data'])
    print(f"Total audio bytes received: {total_bytes}")
asyncio.run(test())
