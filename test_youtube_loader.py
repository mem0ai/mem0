from embedchain.embedchain.loaders.youtube_video import YoutubeVideoLoader

url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

loader = YoutubeVideoLoader()
result = loader.load_data(url)

print("\n✅ DOC ID:", result["doc_id"])
print("\n✅ METADATA:", result["data"][0]["meta_data"].keys())
print("\n✅ ISO TIME:", result["data"][0]["meta_data"].get("published_at_iso"), "\n")