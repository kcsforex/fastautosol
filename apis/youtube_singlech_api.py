# 2026.03.25 18:00
from fastapi import APIRouter
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from googleapiclient.discovery import build
import isodate

# --- Initialize APIRouter & FastMCP ---
router = APIRouter()

mcp = FastMCP("YouTube Analytics", stateless_http=True, transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
api_key = "AIzaSyBzSaapBAb9sfTih5iHefzDeYOtKB8_G7s"
youtube = build("youtube", "v3", developerKey=api_key)

# --- MCP Tool (called by AI / N8N) ---
@mcp.tool(name="get_youtube_metrics")
async def get_channel_stats_mcp(channel:str, maxVideos: int = 5, maxComments: int = 5):
    return await fetch_youtube_singlech(channel, maxVideos, maxComments)

# --- REST Endpoint (called by Dash / browser) ---
@router.get("/metrics/{channel}")
async def get_channel_stats_api(channel:str,  maxVideos:int = 5, maxComments:int = 5):
    return await fetch_youtube_singlech(channel, maxVideos, maxComments)

# --- Main Youtube logic ---
async def fetch_youtube_singlech(channel:str, maxVideos:int = 5, maxComments:int = 5):
    
    ch_response = youtube.channels().list(part="id,snippet,statistics,contentDetails", forHandle=channel).execute()
    if not ch_response.get("items"):
        return {"error": "Channel not found"}

    channel_item = ch_response["items"][0]
    playlist_id = channel_item["contentDetails"]["relatedPlaylists"]["uploads"]
    playlist_response = youtube.playlistItems().list(part="contentDetails",playlistId=playlist_id,maxResults=maxVideos).execute()

    video_ids = [item["contentDetails"]["videoId"] for item in playlist_response.get("items", [])]
    if not video_ids:
        return []

    stats_response = youtube.videos().list(part="snippet,contentDetails,statistics",id=",".join(video_ids)).execute()

    results = []
    for video in stats_response.get("items", []):
        video_id = video["id"]
        stats = video["statistics"]
        snippet = video["snippet"]
        details = video["contentDetails"]

        comments = []
        if int(stats.get("commentCount", 0)) > 0 and int(stats.get("viewCount", 0)) > 1000:
            try:
                comment_response = youtube.commentThreads().list(part="snippet", videoId=video_id, maxResults=maxComments, textFormat="plainText").execute()
                for c_item in comment_response.get("items", []):
                    c_snippet = c_item["snippet"]["topLevelComment"]["snippet"]
                    comments.append({ "c_author": c_snippet["authorDisplayName"], "c_published": c_snippet["publishedAt"], "c_text": c_snippet["textDisplay"][:150], "c_like_count": c_snippet["likeCount"]})
            except Exception as e:
                comments = [{"error": str(e)}]
        else:
            comments = ['Not reach enough views (1000) or zero comments']

        results.append({
            "channel_name": channel_item["snippet"]["title"],
            "subscribers": int(channel_item["statistics"].get("subscriberCount", 0)),
            "video_id": video_id,
            "title": snippet["title"][:50],
            "duration_sec": int(isodate.parse_duration(details.get("duration")).total_seconds()),
            "upload_date": snippet["publishedAt"],
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "comments": comments 
        })

    return results
