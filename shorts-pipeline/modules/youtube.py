import os
import logging

logger = logging.getLogger(__name__)

# force-ssl necessário para comentários e upload de thumbnail
_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
_CATEGORY_TECH = "28"


def _get_credentials(credentials_file, token_file):
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise ImportError(
            "Execute: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )

    creds = None

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                # Token expirado sem renovação possível — re-autorizar
                creds = None

        if not creds:
            # Abre o navegador para autorização (só acontece uma vez)
            flow  = InstalledAppFlow.from_client_secrets_file(credentials_file, _SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_file, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds


def _build_client(credentials_file, token_file):
    from googleapiclient.discovery import build
    creds = _get_credentials(credentials_file, token_file)
    return build("youtube", "v3", credentials=creds)


def upload_video(video_path, title, description, tags, credentials_file,
                 token_file="token.json", privacy="private"):
    """
    Faz upload do vídeo para o YouTube via Data API v3.
    Primeira execução: abre o navegador para autorizar (uma vez só).
    Retorna video_id ou None em caso de falha.
    """
    if not os.path.exists(credentials_file):
        logger.error(
            f"client_secrets.json não encontrado: {credentials_file}\n"
            "Configure em console.cloud.google.com → YouTube Data API v3 → Credenciais."
        )
        return None

    if not os.path.exists(video_path):
        logger.error(f"Vídeo não encontrado: {video_path}")
        return None

    try:
        from googleapiclient.http import MediaFileUpload
        youtube = _build_client(credentials_file, token_file)

        body = {
            "snippet": {
                "title":      title[:100],
                "description": description,
                "tags":       [t[:30] for t in tags[:10]],
                "categoryId": _CATEGORY_TECH,
            },
            "status": {
                "privacyStatus":           privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        media   = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=1024 * 1024)
        request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)

        logger.info(f"Iniciando upload: {title}")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"Upload: {int(status.progress() * 100)}%")

        video_id  = response["id"]
        logger.info(f"Upload concluído ({privacy}): https://youtube.com/shorts/{video_id}")
        return video_id

    except Exception as e:
        logger.error(f"Erro no upload YouTube: {e}")
        return None


def upload_thumbnail(video_id, thumbnail_path, credentials_file, token_file="token.json"):
    """
    Faz upload da thumbnail para o vídeo.
    Requer scope youtube.force-ssl (já incluso em _SCOPES).
    """
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        logger.warning("Thumbnail não encontrada — pulando upload de thumbnail.")
        return False

    try:
        from googleapiclient.http import MediaFileUpload
        youtube = _build_client(credentials_file, token_file)

        media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
        youtube.thumbnails().set(videoId=video_id, media_body=media).execute()

        logger.info(f"Thumbnail enviada para vídeo {video_id}")
        return True

    except Exception as e:
        logger.error(f"Erro ao enviar thumbnail: {e}")
        return False


def post_affiliate_comment(video_id, amazon_link, shopee_link,
                           credentials_file, token_file="token.json"):
    """
    Posta comentário com links de afiliado no vídeo.
    O comentário aparece como o dono do canal.
    Pinagem manual necessária no YouTube Studio (2 cliques).
    """
    lines = ["🔗 Links mencionados no vídeo:"]
    if amazon_link:
        lines.append(f"Amazon → {amazon_link}")
    if shopee_link:
        lines.append(f"Shopee → {shopee_link}")
    lines.append("\n* Links de afiliado — sem custo adicional para você.")

    comment_text = "\n".join(lines)

    if not amazon_link and not shopee_link:
        logger.warning("Sem links de afiliado configurados — comentário não postado.")
        return False

    try:
        youtube = _build_client(credentials_file, token_file)

        youtube.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {"textOriginal": comment_text}
                    },
                }
            },
        ).execute()

        logger.info(f"Comentário de afiliado postado no vídeo {video_id}")
        logger.info("Lembre-se de fixar o comentário no YouTube Studio.")
        return True

    except Exception as e:
        logger.error(f"Erro ao postar comentário: {e}")
        return False
