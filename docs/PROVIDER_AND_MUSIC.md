# External Providers, Music Catalog and Playback Rights

Music is explicitly in Phase 1. The expected conversation is “搜索周杰伦的歌，给我歌曲列表，点一下播放”. The result must distinguish search, rights verification, and the play/open action. **Do not guarantee that an arbitrary commercial master recording can be streamed inside Adex without a streaming grant.**

## Provider interfaces

```python
from typing import Protocol

class MusicCatalogProvider(Protocol):
    async def search(self, query: str, artist: str | None, region: str, limit: int): ...

class PlaybackProvider(Protocol):
    async def resolve(self, user_id: str, track_ref: str, device: dict): ...
```

Music card `availability` = `INLINE_LICENSED | USER_LIBRARY | PROVIDER_OPEN | UNAVAILABLE`. Inline actions require a valid authenticated URI and expiry; deep links require an HTTPS fallback. Catalog results must include `provider/track_id/title/artists/source_url`. Track-level license and user-subscription capability are checked at action time.

## Legal demonstration plan

1. Use a real, contract-allowed search catalog to list songs by the named artist. For each item, provide an official music-platform link. If the API is not authorized or available, label `BLOCKED_EXTERNAL`.
2. The integration test **plays user-owned or explicitly licensed fixture audio** using HTMLMediaElement/WKWebView media player; includes play/pause/next/progress.
3. An unlicensed commercial song must trigger `PROVIDER_OPEN` rather than raw MP3 download or streamed proxy; no DRM circumvention.
4. User audio uploads require ownership/authorization acknowledgement and App-owned local persistent disk, protected by API ACL (no public media directory); no general public redistribution.
5. A metadata search response may expose a short preview URL subject to source restrictions; do **not** assume permission for entertainment playback. Apple iTunes Search API documentation restricts its promotional assets: https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/
6. Full Apple MusicKit integration is optional future provider work and may require developer membership, tokens and per-user subscription: https://developer.apple.com/documentation/AppleMusicAPI/generating-developer-tokens

## Additional sources

- Web search: authorized search API + content timestamp and citations.
- Hotels: do not claim verified rates, inventory or booking success from a text-search snippet.
- Maps/POI: provider IDs, geolocation, TTL and scope; user location protected.
- Model: authorized commercial API available from the ECS region, variable providers for redundancy.
