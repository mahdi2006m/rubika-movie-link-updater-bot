import os
import json
import sqlite3
import logging
import re
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from rapidfuzz import fuzz

load_dotenv()
logger = logging.getLogger(__name__)

DB_NAME = os.getenv("DB_PATH", "film_DB.db")
ALLOW_QUALITY = ('480p', '720p', '1080p', '4K')
ALLOW_LANGUAGE_TYPE = ('original', 'dubbed')


def get_connection():
    conn = sqlite3.connect(
        DB_NAME,
        timeout=10.0,
        isolation_level=None,  # autocommit mode
        check_same_thread=False  # اجازه استفاده از چند thread
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript('''
                           CREATE TABLE IF NOT EXISTS movies
                               (
                                   id INTEGER
                                       PRIMARY KEY AUTOINCREMENT,
                                   title TEXT NOT NULL,
                                   tags TEXT DEFAULT '[]',
                                   chat_id TEXT NOT NULL,
                                   message_id TEXT NOT NULL,
                                   source Text,
                                   "index" INTEGER,
                                   is_anime INTEGER DEFAULT 0,
                                   message_type INTEGER,
                                   online_watchable INTEGER DEFAULT 0,
                                   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                   UNIQUE (chat_id, message_id)
                               );

                           CREATE TABLE IF NOT EXISTS releases
                               (
                                   id INTEGER
                                       PRIMARY KEY AUTOINCREMENT,
                                   movie_id INTEGER NOT NULL,
                                   language_type TEXT NOT NULL
                                       CHECK (language_type IN ('original', 'dubbed')),
                                   UNIQUE (movie_id, language_type),
                                   FOREIGN KEY (movie_id) REFERENCES movies (id) ON DELETE CASCADE
                               );

                           CREATE TABLE IF NOT EXISTS quality
                               (
                                   id INTEGER
                                       PRIMARY KEY AUTOINCREMENT,
                                   release_id INTEGER NOT NULL,
                                   quality TEXT NOT NULL
                                       CHECK (quality IN ('480p', '720p', '1080p', '4K')),
                                   download_link TEXT NOT NULL,
                                   UNIQUE (release_id, quality),
                                   FOREIGN KEY (release_id) REFERENCES releases (id) ON DELETE CASCADE
                               );

                           CREATE TABLE IF NOT EXISTS subtitles
                               (
                                   id INTEGER
                                       PRIMARY KEY AUTOINCREMENT,
                                   quality_id INTEGER NOT NULL,
                                   download_link TEXT NOT NULL,
                                   UNIQUE (quality_id, download_link),
                                   FOREIGN KEY (quality_id) REFERENCES quality (id) ON DELETE CASCADE
                               );



                           CREATE TABLE IF NOT EXISTS failed_movies
                               (
                                   id INTEGER
                                       PRIMARY KEY AUTOINCREMENT,
                                   movie_id INTEGER NOT NULL,
                                   title TEXT NOT NULL,
                                   search_query TEXT,
                                   source TEXT,
                                   error TEXT,
                                   attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                   UNIQUE (title, movie_id),
                                   FOREIGN KEY (movie_id) REFERENCES movies (id) ON DELETE CASCADE
                               );



                           ------------------------------------------------------------
                           -- تریگرهای جدول quality
                           ------------------------------------------------------------
                           CREATE TRIGGER if NOT EXISTS trg_quality_insert
                               AFTER
                           INSERT
                               ON quality
                           BEGIN
                           UPDATE movies
                              SET updated_at = CURRENT_TIMESTAMP
                            WHERE id = (SELECT r.movie_id FROM releases r WHERE r.id = new.release_id);
                           END;

                           CREATE TRIGGER if NOT EXISTS trg_quality_update
                               AFTER
                           UPDATE on quality
                           BEGIN
                           -- به‌روزرسانی فیلم جدید (release_id فعلی)
                           UPDATE movies
                              SET updated_at = CURRENT_TIMESTAMP
                            WHERE id = (SELECT r.movie_id FROM releases r WHERE r.id = new.release_id);

                           -- اگر release_id تغییر کرده باشد، فیلم قبلی هم به‌روز شود
                           UPDATE movies
                              SET updated_at = CURRENT_TIMESTAMP
                            WHERE old.release_id != new.release_id
                              AND id = (SELECT r.movie_id FROM releases r WHERE r.id = old.release_id);
                           END;

                           CREATE TRIGGER if NOT EXISTS trg_quality_delete
                               AFTER
                           DELETE
                               ON quality
                           BEGIN
                           UPDATE movies
                              SET updated_at = CURRENT_TIMESTAMP
                            WHERE id = (SELECT r.movie_id FROM releases r WHERE r.id = old.release_id);
                           END;

                           ------------------------------------------------------------
                           -- تریگرهای جدول subtitles
                           ------------------------------------------------------------
                           CREATE TRIGGER if NOT EXISTS trg_subtitles_insert
                               AFTER
                           INSERT
                               ON subtitles
                           BEGIN
                           UPDATE movies
                              SET updated_at = CURRENT_TIMESTAMP
                            WHERE id = (SELECT r.movie_id
                                          FROM releases r
                                                   JOIN quality q
                                                   ON q.release_id = r.id
                                         WHERE q.id = new.quality_id);
                           END;

                           CREATE TRIGGER if NOT EXISTS trg_subtitles_update
                               AFTER
                           UPDATE on subtitles
                           BEGIN
                           -- به‌روزرسانی فیلمی که quality_id جدید به آن اشاره می‌کند
                           UPDATE movies
                              SET updated_at = CURRENT_TIMESTAMP
                            WHERE id = (SELECT r.movie_id
                                          FROM releases r
                                                   JOIN quality q
                                                   ON q.release_id = r.id
                                         WHERE q.id = new.quality_id);

                           -- اگر quality_id تغییر کرده، فیلم قبلی هم به‌روزرسانی شود
                           UPDATE movies
                              SET updated_at = CURRENT_TIMESTAMP
                            WHERE old.quality_id != new.quality_id
                              AND id = (SELECT r.movie_id
                                          FROM releases r
                                                   JOIN quality q
                                                   ON q.release_id = r.id
                                         WHERE q.id = old.quality_id);
                           END;

                           CREATE TRIGGER if NOT EXISTS trg_subtitles_delete
                               AFTER
                           DELETE
                               ON subtitles
                           BEGIN
                           UPDATE movies
                              SET updated_at = CURRENT_TIMESTAMP
                            WHERE id = (SELECT r.movie_id
                                          FROM releases r
                                                   JOIN quality q
                                                   ON q.release_id = r.id
                                         WHERE q.id = old.quality_id);
                           END;
                           ''')
    logger.info("✅ دیتابیس با موفقیت مقداردهی اولیه شد.")


class DatabaseError(Exception):
    """خطای سفارشی برای عملیات دیتابیس"""
    pass


# ----------------------------------------------------------------------
# Movie CRUD
# ----------------------------------------------------------------------
def get_or_create_movie(title: str,
                        tags: Optional[List[str]] = None,
                        chat_id: Optional[str] = None,
                        message_id: Optional[str] = None,
                        source: Optional[str] = None,
                        is_anime: bool = False,
                        message_type: int = 1,
                        online_watchable: bool = False) -> int:
    """یک فیلم جدید ایجاد می‌کند و id آن را برمی‌گرداند."""
    tags_json = json.dumps(sorted(tags) if tags else [])
    online_watchable = int(online_watchable)
    is_anime = int(is_anime)
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO movies (title, tags, chat_id, message_id, SOURCE, is_anime, message_type, online_watchable) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (title, tags_json, chat_id, message_id, source, is_anime, message_type, online_watchable)
            )
            if cursor.rowcount == 0:
                # درج انجام نشد (فیلم از قبل وجود داشته)
                cursor = conn.execute(
                    "SELECT id FROM movies WHERE chat_id = ? AND message_id = ?",
                    (chat_id, message_id)
                )
                row = cursor.fetchone()
                if row is None:
                    raise DatabaseError("خطای غیرمنتظره: فیلم یافت نشد.")
                return row["id"]
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to create movie: {e}")


def get_movie(movie_id: int) -> Optional[Dict[str, Any]]:
    """یک فیلم را با id مشخص برمی‌گرداند (tags به صورت list)"""
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM movies WHERE id = ?", (movie_id,)).fetchone()
            if row:
                movie = dict(row)
                movie['tags'] = json.loads(movie['tags'])
                movie['online_watchable'] = bool(movie['online_watchable'])
                movie['is_anime'] = bool(movie['is_anime'])
                return movie
            return None
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get movie: {e}")


def get_all_movies() -> List[Dict[str, Any]]:
    """لیست همه فیلم‌ها را برمی‌گرداند."""
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM movies ORDER BY created_at DESC").fetchall()
            movies = []
            for row in rows:
                movie = dict(row)
                movie['tags'] = json.loads(movie['tags'])
                movie['online_watchable'] = bool(movie['online_watchable'])
                movies.append(movie)
            return movies
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get movies: {e}")


def update_movie(movie_id: int, **kwargs) -> bool:
    """فیلدهای داده شده را برای یک فیلم به‌روزرسانی می‌کند.
       kwargs می‌تواند شامل title, tags, chat_id, message_id باشد.
       tags باید list باشد."""
    allowed_fields = {'title', 'tags', 'chat_id', 'message_id'}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not updates:
        return False

    if 'tags' in updates:
        updates['tags'] = json.dumps(updates['tags'])

    set_clause = ', '.join(f"{key} = ?" for key in updates)
    values = list(updates.values())
    values.append(movie_id)

    try:
        with get_connection() as conn:
            conn.execute(
                f"UPDATE movies SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to update movie: {e}")


def delete_movie(movie_id: int) -> bool:
    """یک فیلم را حذف می‌کند (با CASCADE تمام releaseها و زیرمجموعه‌ها حذف می‌شوند)."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to delete movie: {e}")


def update_movie_index(movie_id: int, new_index: int) -> None:
    """
    فقط ستون 'index' رکورد مورد نظر را به‌روز می‌کند.

    Args:
        movie_id: شناسه فیلم
        new_index: مقدار جدید برای ایندکس
    """
    try:
        with get_connection() as conn:
            # استفاده از commit صریح و timeout بیشتر
            # conn.execute('PRAGMA busy_timeout = 30000')  # 30 ثانیه timeout برای قفل
            conn.execute(
                'UPDATE movies SET "index" = ? WHERE id = ?',
                (new_index, movie_id)
            )
            conn.commit()
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to update movie index: {e}")


# ----------------------------------------------------------------------
# Release CRUD
# ----------------------------------------------------------------------
def get_or_create_release(movie_id: int, language_type: str) -> int:
    """یک release جدید ایجاد می‌کند. language_type باید 'original' یا 'dubbed' باشد."""
    if language_type not in ALLOW_LANGUAGE_TYPE:
        raise ValueError("language_type must be 'original' or 'dubbed'")
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO releases (movie_id, language_type) VALUES (?, ?)",
                (movie_id, language_type)
            )

            if cursor.rowcount == 0:
                # درج انجام نشد (فیلم از قبل وجود داشته)
                cursor = conn.execute(
                    "SELECT id FROM releases WHERE movie_id = ? AND language_type = ?",
                    (movie_id, language_type)
                )
                row = cursor.fetchone()
                if row is None:
                    raise DatabaseError("خطای غیرمنتظره: ریلیز یافت نشد.")
                return row["id"]

            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to create release: {e}")


def get_release(release_id: int) -> Optional[Dict[str, Any]]:
    """یک release را با id مشخص برمی‌گرداند."""
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM releases WHERE id = ?", (release_id,)).fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get release: {e}")


def get_releases_by_movie(movie_id: int) -> List[Dict[str, Any]]:
    """همه releaseهای مربوط به یک فیلم را برمی‌گرداند."""
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM releases WHERE movie_id = ?", (movie_id,)
            ).fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get releases: {e}")


def update_release(release_id: int, language_type: str) -> bool:
    """نوع زبان یک release را به‌روزرسانی می‌کند."""
    if language_type not in ALLOW_LANGUAGE_TYPE:
        raise ValueError("language_type must be 'original' or 'dubbed'")
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "UPDATE releases SET language_type = ? WHERE id = ?",
                (language_type, release_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to update release: {e}")


def delete_release(release_id: int) -> bool:
    """یک release را حذف می‌کند (quality و subtitleهای مرتبط CASCADE می‌شوند)."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM releases WHERE id = ?", (release_id,))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to delete release: {e}")


# ----------------------------------------------------------------------
# Quality CRUD
# ----------------------------------------------------------------------
def get_or_create_quality(release_id: int, quality: str, download_link: str) -> int:
    """یک quality جدید ایجاد می‌کند. quality باید یکی از '480p','720p','1080p','4K' باشد."""
    valid_qualities = ALLOW_QUALITY
    if quality not in valid_qualities:
        raise ValueError(f"quality must be one of {valid_qualities}")
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO quality (release_id, quality, download_link) VALUES (?, ?, ?)",
                (release_id, quality, download_link)
            )
            if cursor.rowcount == 0:
                cursor = conn.execute(
                    "SELECT id FROM quality WHERE release_id = ? AND quality = ?",
                    (release_id, quality)
                )
                row = cursor.fetchone()
                if row is None:
                    raise DatabaseError("خطای غیرمنتظره: کیفیت یافت نشد.")
                return row["id"]
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to create quality: {e}")


def get_quality(quality_id: int) -> Optional[Dict[str, Any]]:
    """یک quality را با id مشخص برمی‌گرداند."""
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM quality WHERE id = ?", (quality_id,)
            ).fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get quality: {e}")


def get_qualities_by_release(release_id: int) -> List[Dict[str, Any]]:
    """همه qualityهای مربوط به یک release را برمی‌گرداند."""
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM quality WHERE release_id = ?", (release_id,)
            ).fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get qualities: {e}")


def update_quality(quality_id: int, quality: Optional[str] = None,
                   download_link: Optional[str] = None) -> bool:
    """فیلدهای quality (سطح کیفیت و/یا لینک دانلود) را به‌روزرسانی می‌کند."""
    valid_qualities = ALLOW_QUALITY
    updates = {}
    if quality is not None:
        if quality not in valid_qualities:
            raise ValueError(f"quality must be one of {valid_qualities}")
        updates['quality'] = quality
    if download_link is not None:
        updates['download_link'] = download_link

    if not updates:
        return False

    set_clause = ', '.join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [quality_id]

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE quality SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to update quality: {e}")


def delete_quality(quality_id: int) -> bool:
    """یک quality را حذف می‌کند (subtitleهای مرتبط CASCADE می‌شوند)."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM quality WHERE id = ?", (quality_id,))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to delete quality: {e}")


# ----------------------------------------------------------------------
# Subtitle CRUD
# ----------------------------------------------------------------------
def get_or_create_subtitle(quality_id: int, download_link: str) -> int:
    """یک زیرنویس جدید ایجاد می‌کند."""
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO subtitles (quality_id, download_link) VALUES (?, ?)",
                (quality_id, download_link)
            )
            if cursor.rowcount == 0:
                cursor = conn.execute(
                    "SELECT id FROM subtitles WHERE quality_id = ? AND download_link = ?",
                    (quality_id, download_link)
                )
                row = cursor.fetchone()
                if row is None:
                    raise DatabaseError("خطای غیرمنتظره: کیفیت یافت نشد.")
                return row["id"]
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to create subtitle: {e}")


def get_subtitle(subtitle_id: int) -> Optional[Dict[str, Any]]:
    """یک زیرنویس را با id مشخص برمی‌گرداند."""
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM subtitles WHERE id = ?", (subtitle_id,)
            ).fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get subtitle: {e}")


def get_subtitles_by_quality(quality_id: int) -> List[Dict[str, Any]]:
    """همه زیرنویس‌های مربوط به یک quality را برمی‌گرداند."""
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM subtitles WHERE quality_id = ?", (quality_id,)
            ).fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get subtitles: {e}")


def update_subtitle(subtitle_id: int, download_link: str) -> bool:
    """لینک دانلود یک زیرنویس را به‌روزرسانی می‌کند."""
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "UPDATE subtitles SET download_link = ? WHERE id = ?",
                (download_link, subtitle_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to update subtitle: {e}")


def delete_subtitle(subtitle_id: int) -> bool:
    """یک زیرنویس را حذف می‌کند."""
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM subtitles WHERE id = ?", (subtitle_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to delete subtitle: {e}")


# ----------------------------------------------------------------------
# Failed_movie CRUD
# ----------------------------------------------------------------------
def add_failed_movie(
        title: str,
        error: str,
        movie_id: Optional[int] = None,
        search_query: Optional[str] = None,
        source: Optional[str] = None,
        db_path: str = "your_database.db"
) -> int:
    """
    ثبت یا به‌روزرسانی فیلم ناموفق در جدول failed_movies.
    اگر ترکیب (title, movie_id) وجود داشته باشد، خطا و زمان آن به‌روز می‌شود.
    Returns:
        آخرین id درج شده (در صورت به‌روزرسانی، id قبلی را برمی‌گرداند).
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO failed_movies (title, movie_id, search_query, source, error, attempted_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(title, movie_id) DO UPDATE SET error = excluded.error,
                                                               search_query = excluded.search_query,
                                                               source = excluded.source,
                                                               attempted_at = CURRENT_TIMESTAMP
                """,
                (title, movie_id, search_query, source, error)
            )
            conn.commit()
            if cursor.lastrowid:
                return cursor.lastrowid
            else:
                row = conn.execute(
                    "SELECT id FROM failed_movies WHERE title = ? AND movie_id = ?",
                    (title, movie_id)
                ).fetchone()
                return row['id'] if row else -1
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to upsert failed movie: {e}")


def get_failed_movie(movie_id: int) -> Optional[Dict[str, Any]]:
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM failed_movies WHERE movie_id = ?", (movie_id,)).fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get failed movie: {e}")


def delete_failed_movie(failed_id: int) -> bool:
    try:
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM failed_movies WHERE id = ?", (failed_id,))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to delete failed movie: {e}")


def get_all_failed_movies() -> List[Dict[str, Any]]:
    """لیست همه فیلم‌هایی که قبلاً یافت نشده‌اند، به ترتیب جدیدترین اول."""
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM failed_movies ORDER BY attempted_at DESC").fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get failed movies: {e}")


def delete_failed_movie_by_movie_id(movie_id: int) -> bool:
    """حذف یک فیلم ناموفق بر اساس movie_id"""
    try:
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM failed_movies WHERE movie_id = ?", (movie_id,))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to delete failed movie by movie_id: {e}")


def clear_all_failed_movies() -> bool:
    """پاک کردن تمام لیست فیلم‌های ناموفق"""
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM failed_movies")
            conn.commit()
            return True
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to clear failed movies: {e}")


# ----------------------------------------------------------------------
# تابع کمکی: دریافت اطلاعات کامل یک فیلم با تمام زیرمجموعه‌ها
# ----------------------------------------------------------------------
def get_movie_full(movie_id: int) -> Optional[Dict[str, Any]]:
    """اطلاعات کامل یک فیلم شامل releaseها، qualityها و subtitleها را برمی‌گرداند."""
    movie = get_movie(movie_id)
    if not movie:
        return None

    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            releases = conn.execute(
                "SELECT * FROM releases WHERE movie_id = ?", (movie_id,)
            ).fetchall()
            releases_dict = {}
            for rel in releases:
                rel_dict = dict(rel)
                # دریافت qualityهای هر release
                qualities = conn.execute(
                    "SELECT * FROM quality WHERE release_id = ?", (rel_dict['id'],)
                ).fetchall()
                qualities_dict = {}
                for qual in qualities:
                    qual_dict = dict(qual)
                    # دریافت subtitleهای هر quality
                    subs = conn.execute(
                        "SELECT * FROM subtitles WHERE quality_id = ?", (qual_dict['id'],)
                    ).fetchall()
                    qual_dict['subtitles'] = [dict(sub) for sub in subs]
                    qualities_dict[f"{qual['quality']}"] = qual_dict
                rel_dict['qualities'] = qualities_dict
                releases_dict[f'{rel['language_type']}'] = rel_dict
            movie['releases'] = releases_dict
            return movie
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get full movie data: {e}")


def search_movies_by_tag(tag):
    with get_connection() as conn:
        # json_each مقدار هر عنصر رو توی ستون value میریزه
        rows = conn.execute(
            """SELECT DISTINCT movies.*
                 FROM movies, JSON_EACH(movies.tags)
                WHERE json_each.value = ?""",
            (tag,)
        ).fetchall()
    return rows


def create_full_movie_type1(message_info, channel_guid, message_id):
    try:
        movie_id = get_or_create_movie(message_info.get('movie_name'), message_info.get('movie_name').split(' / '),
                                       channel_guid,
                                       message_id,
                                       message_info.get('source'),
                                       is_anime=message_info.get('is_anime'),
                                       message_type=1,
                                       online_watchable=message_info.get('online_watchable'))
        for rel, quality_list in message_info.get('versions').items():
            rel_id = get_or_create_release(movie_id, rel)
            for quality in quality_list:
                quality_id = get_or_create_quality(rel_id, quality.get('quality') + 'p', quality.get('links')[0])
                if quality.get('subtitle_link', None):
                    get_or_create_subtitle(quality_id, quality.get('subtitle_link')[0])
    except Exception as e:
        raise DatabaseError(f"Failed to create full movie data: {e}")
    return movie_id


def create_full_movie_type2(message_info, channel_guid, message_id):
    try:
        movie_id = get_or_create_movie(message_info.get('movie_name'), message_info.get('movie_name').split(' / '),
                                       channel_guid,
                                       message_id,
                                       message_info.get('source'),
                                       message_type=2)
        rel_id = get_or_create_release(movie_id, 'dubbed')
        get_or_create_quality(rel_id, message_info.get('quality') + 'p', message_info.get('download_link'))
    except Exception as e:
        raise DatabaseError(f"Failed to create full movie data: {e}")
    return movie_id


def update_movie_links(full_movie, new_links_data):
    movie_title = full_movie.get('title')
    result = None

    # دریافت دیتای لینک‌های جدید برای این فیلم خاص
    movie_links = new_links_data.get(movie_title, {})

    for rel, rel_info in full_movie.get('releases').items():
        qualities = rel_info.get('qualities', {})

        # فقط لینک‌های مربوط به همین زبان (rel) را استخراج می‌کنیم (مثلا فقط original یا فقط dubbed)
        rel_links = movie_links.get(rel, {})

        for quality, quality_info in qualities.items():
            quality_id = quality_info.get('id')
            sub = quality_info.get('subtitles', [])

            has_sub = len(sub) > 0
            sub_id = sub[0].get('id') if has_sub else None

            # بررسی وجود لینک برای این کیفیت خاص در همان زبان
            q = rel_links.get(quality)
            if q is None:
                continue

            new_link = q.get('link')
            new_sub_link = q.get('sub_link')

            q_success = False
            s_success = False

            # آپدیت لینک دانلود فیلم
            if new_link is not None:
                q_success = update_quality(quality_id, download_link=new_link)

            # آپدیت لینک زیرنویس (در صورت وجود)
            if new_sub_link is not None and has_sub and sub_id:
                s_success = update_subtitle(sub_id, new_sub_link)

            if q_success or s_success:
                result = True

    return result


# ----------------------------------------------------------------------
# 🔍 جستجوی هوشمند فیلم‌ها
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# 🔍 توابع جستجوی هوشمند و نرمال‌سازی
# ----------------------------------------------------------------------
def normalize_text(text: str) -> str:
    """نرمال‌سازی متن فارسی/انگلیسی برای مقایسه دقیق‌تر"""
    if not text: return ""
    text = text.replace('ي', 'ی').replace('ك', 'ک').replace('ة', 'ه')
    text = __import__('re').sub(r'[\u200c\u200b\u200d\-\_\.\,\!\?]+', ' ', text)
    return __import__('re').sub(r'\s+', ' ', text).strip().lower()


def search_movies_smart(query: str, limit: int = 20, threshold: int = 45) -> list:
    """
    جستجوی هوشمند بهینه‌شده برای ساختار:
      title: "english_name / نام_فارسی"
      tags: ["نام_فارسی", "english_name"]
    """
    import re
    from rapidfuzz import fuzz

    def norm(text):
        if not text: return ""
        text = str(text).strip().lower()
        # یکسان‌سازی حروف فارسی/عربی
        text = text.replace('ي', 'ی').replace('ك', 'ک').replace('ة', 'ه')
        text = text.replace('ؤ', 'و').replace('إ', 'ا').replace('أ', 'ا').replace('آ', 'ا')
        # حذف نویزها و فاصله‌های اضافی
        text = re.sub(r'[\u200c\u200b\u200d\-\_\.\,\!\?\(\)\[\]«»]+', ' ', text)
        return re.sub(r'\s+', ' ', text).strip()

    q = norm(query)
    if not q: return []

    all_movies = get_all_movies()
    scored = []

    for m in all_movies:
        # ۱. جدا کردن title با / و نرمال‌سازی هر بخش
        raw_title = m.get('title', '')
        title_parts = [norm(p) for p in raw_title.split('/') if norm(p)]

        # ۲. نرمال‌سازی تگ‌ها
        raw_tags = m.get('tags') or []
        tag_parts = [norm(t) for t in raw_tags if norm(t)]

        # ترکیب همه متن‌های قابل جستجو (اولویت با title)
        search_texts = title_parts + tag_parts
        if not search_texts:
            continue

        # ۳. محاسبه بهترین امتیاز
        best_score = 0
        for txt in search_texts:
            # تطابق فازی پایه
            score = fuzz.partial_ratio(q, txt)

            # 🔥 تقویت امتیاز برای تطابق زیررشته‌ای دقیق
            if q in txt or txt in q:
                score = max(score, 95)
            # تقویت بیشتر اگر دقیقاً از اول شروع بشه
            if txt.startswith(q):
                score = max(score, 90)

            if score > best_score:
                best_score = score

        if best_score >= threshold:
            scored.append((m, best_score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [m for m, _ in scored[:limit]]


def update_movie_full(movie_id: int, updates: dict) -> bool:
    """آپدیت چند فیلد به صورت اتمیک"""
    allowed = {'title', 'tags', 'source', 'is_anime', 'online_watchable', 'index'}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered: return False

    try:
        with get_connection() as conn:
            sets, vals = [], []
            for k, v in filtered.items():
                if k == 'tags': v = __import__('json').dumps(v) if isinstance(v, list) else v
                sets.append(f"{k} = ?")
                vals.append(v)
            vals.append(movie_id)
            conn.execute(f"UPDATE movies SET {', '.join(sets)}, updated_at=CURRENT_TIMESTAMP WHERE id=?", vals)
            conn.commit()
            return True
    except Exception:
        return False
