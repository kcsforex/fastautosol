# 2026.03.26 14.00 - ASYNC MULTI-CHANNEL YOUTUBE API

from fastapi import APIRouter
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import aiohttp
import asyncio
import isodate
from pydantic import BaseModel

router = APIRouter()
mcp = FastMCP( "YouTube Analytics", stateless_http=True, transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
API_KEY = "AIzaSyBzSaapBAb9sfTih5iHefzDeYOtKB8_G7s"
BASE_URL = "https://www.googleapis.com/youtube/v3"
semaphore = asyncio.Semaphore(5)

# --- GENERIC YT REQUEST ---
async def yt_get(session, endpoint, params):
    params["key"] = API_KEY
    async with semaphore:
        async with session.get(f"{BASE_URL}/{endpoint}", params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"YT API error {resp.status}: {text}")
            return await resp.json()

class ChannelRequest(BaseModel):
    channels: list[str]
    maxVideos: int = 5
    maxComments: int = 3

# --- MCP TOOL (MULTI CHANNEL) ---
@mcp.tool(name="get_youtube_metrics")
async def get_channel_stats_mcp(channels: list[str], maxVideos: int = 5, maxComments: int = 3):
    return await fetch_youtube_multich(channels, maxVideos, maxComments)

# --- REST ENDPOINT (MULTI CHANNEL) ---
@router.post("/metrics")
async def get_channel_stats_api(req: ChannelRequest):
    return await fetch_youtube_multich(req.channels, req.maxVideos, req.maxComments)

# --- MAIN MULTI-CHANNEL LOGIC ---
async def fetch_youtube_multich(channels: list[str], maxVideos: int = 5, maxComments: int = 5):
  
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async def bounded_fetch(channel):
            async with semaphore:
                return await fetch_single_channel(session, channel, maxVideos, maxComments)
        tasks = [bounded_fetch(ch) for ch in channels]
        results = await asyncio.gather(*tasks)
        return [item for sublist in results for item in sublist]

# --- SINGLE CHANNEL LOGIC ---
async def fetch_single_channel(session, channel, maxVideos, maxComments):
    try:
        # --- CHANNEL ---
        ch_data = await yt_get(session, "channels", {"part": "id,snippet,statistics, contentDetails","forHandle": channel})
        if not ch_data.get("items"):
            return [{"channel": channel, "error": "Channel not found"}]

        channel_item = ch_data["items"][0]
        playlist_id = channel_item["contentDetails"]["relatedPlaylists"]["uploads"]
        pl_data = await yt_get(session, "playlistItems", {"part": "contentDetails","playlistId": playlist_id,"maxResults": maxVideos})
        video_ids = [ item["contentDetails"]["videoId"]  for item in pl_data.get("items", [])]
        if not video_ids:
            return []

        vids_data = await yt_get(session, "videos", { "part": "snippet,contentDetails,statistics", "id": ",".join(video_ids)})
        results = []
        for video in vids_data.get("items", []):
            video_id = video["id"]
            stats = video["statistics"]
            snippet = video["snippet"]
            details = video["contentDetails"]
            duration_sec = int(isodate.parse_duration(details["duration"]).total_seconds())

            comments = [] # --- COMMENTS (quota-heavy, conditional) ---
            if int(stats.get("commentCount", 0)) > 0:
                try:
                    c_data = await yt_get(session, "commentThreads", { "part": "snippet", "videoId": video_id, "maxResults": maxComments, "textFormat": "plainText"})
                    for c_item in c_data.get("items", []):
                        c = c_item["snippet"]["topLevelComment"]["snippet"]
                        comments.append({ "c_author": c["authorDisplayName"], "c_published": c["publishedAt"], "c_text": c["textDisplay"][:150], "c_like_count": c["likeCount"]})
                except Exception as e:
                    comments = [{"error": str(e)}]

            results.append({ 
                "channel_name": channel_item["snippet"]["title"], 
                "subscribers": int( channel_item["statistics"].get("subscriberCount", 0)),
                "video_id": video_id,
                "title": snippet["title"][:50],
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
