# 2026.03.27 18.00 - UNIFIED YOUTUBE API

from fastapi import FastAPI, APIRouter, Query
from pydantic import BaseModel, Field, field_validator
from typing import List
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import aiohttp
import asyncio
import isodate

# --- CONFIG ---
API_KEY = "AIzaSyBzSaapBAb9sfTih5iHefzDeYOtKB8_G7s"
BASE_URL = "https://www.googleapis.com/youtube/v3"
semaphore = asyncio.Semaphore(5)
router = APIRouter()
mcp = FastMCP("YouTube Analytics",  stateless_http=True, transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))

# --- PYDANTIC MODEL ---
class YouTubeRequest(BaseModel):
    channels: List[str] = Field(..., min_length=1, description="List of YouTube channel handles")
    maxVideos: int = Field(5, ge=1, le=50)
    maxComments: int = Field(5, ge=0, le=50)

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v):
        if not v:
            raise ValueError("channels list cannot be empty")
        for ch in v:
            if not ch.startswith("@"):
                raise ValueError(f"Invalid channel handle: {ch}")
        return v

# --- GENERIC YT REQUEST ---
async def yt_get(session, endpoint, params):
    params["key"] = API_KEY
    async with semaphore:
        async with session.get(f"{BASE_URL}/{endpoint}", params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"YT API error {resp.status}: {text}")
            return await resp.json()

# --- MCP TOOL ---
@mcp.tool(name="get_youtube_metrics")
async def get_youtube_metrics_tool(channels: List[str], maxVideos: int = 5, maxComments: int = 5):
    return await fetch_youtube_multich(channels, maxVideos, maxComments)

# --- REST POST (MAIN) ---
@router.post("/metrics")
async def get_youtube_metrics_api(req: YouTubeRequest):
    return await fetch_youtube_multich(req.channels, req.maxVideos, req.maxComments)

# --- OPTIONAL GET (for testing in webbrowser) ---
@router.get("/metrics")
async def get_youtube_metrics_get(channels: List[str] = Query(...), maxVideos: int = 5, maxComments: int = 5):
    return await fetch_youtube_multich(channels, maxVideos, maxComments)

# --- MULTI FETCH ---
async def fetch_youtube_multich(channels, maxVideos, maxComments):
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = [ fetch_single_channel(session, ch, maxVideos, maxComments) for ch in channels]
        results = await asyncio.gather(*tasks)
        return [item for sublist in results for item in sublist]

# --- SINGLE CHANNEL ---
async def fetch_single_channel(session, channel, maxVideos, maxComments):
    try:

        ch_data = await yt_get(session, "channels", { "part": "id,snippet,statistics,contentDetails", "forHandle": channel})
        if not ch_data.get("items"):
            return [{"channel": channel, "error": "Channel not found"}]
        ch_item = ch_data["items"][0]
        playlist_id = ch_item["contentDetails"]["relatedPlaylists"]["uploads"]

        pl_data = await yt_get(session, "playlistItems", { "part": "contentDetails", "playlistId": playlist_id, "maxResults": maxVideos})
        video_ids = [ item["contentDetails"]["videoId"] for item in pl_data.get("items", []) ]
        if not video_ids:
            return []

        vids_data = await yt_get(session, "videos", { "part": "snippet,contentDetails,statistics", "id": ",".join(video_ids)})
        results = []
        for video in vids_data.get("items", []):
            video_id = video["id"]
            stats = video["statistics"]
            snippet = video["snippet"]
            details = video["contentDetails"]
            duration_sec = int( isodate.parse_duration(details["duration"]).total_seconds())
            
            comments = []
            if int(stats.get("commentCount", 0)) > 0:
                try:
                    c_data = await yt_get(session, "commentThreads", {"part": "snippet", "videoId": video_id, "maxResults": maxComments, "textFormat": "plainText"})
                    for c_item in c_data.get("items", []):
                        c_id = c_item["snippet"]["topLevelComment"]["id"]
                        c = c_item["snippet"]["topLevelComment"]["snippet"]
                        comments.append({"c_id": c_id, "c_author": c["authorDisplayName"], "c_published": c["publishedAt"], "c_text": c["textDisplay"][:150], "c_like_count": c["likeCount"]})

                except Exception as e:
                    comments = [{"error": str(e)}]

            results.append({
                "channel_name": ch_item["snippet"]["title"],
                "video_id": video_id,
                "title": snippet["title"][:75],
                "duration_sec": duration_sec,
                "upload_date": snippet["publishedAt"],
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats.get("likeCount", 0)),
                "comment_count": int(stats.get("commentCount", 0)),
                "comments": comments
            })

        return results

    except Exception as e:
        return [{"channel": channel, "error": str(e)}]
