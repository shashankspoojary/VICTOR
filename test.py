import edge_tts, asyncio
async def test():
 communicate = edge_tts.Communicate('test', 'en-US-ChristopherNeural')
 async for chunk in communicate.stream():
  print(chunk['type'])
  break
asyncio.run(test())
