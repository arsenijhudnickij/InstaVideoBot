import yt_dlp
import logging

logger = logging.getLogger(__name__)

def get_video_url(url: str) -> tuple[str | None, str]:
    """
    Возвращает (ссылка, расширение) через yt-dlp без скачивания.
    """
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio/best",
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("url"), info.get("ext", "mp4")
    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
        return None, ""
