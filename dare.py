import pyfiglet
import requests
import json
from bs4 import BeautifulSoup
import re
from datetime import datetime
import sys
import time
import os
import phonenumbers
from phonenumbers import geocoder, carrier, timezone
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import subprocess
import platform
import hashlib
import socket
import csv
from typing import Dict, List, Optional, Any
import concurrent.futures
from urllib.parse import urlparse, quote_plus
import signal
import random
import string
import tempfile


class Config:
    DEFAULT_TIMEOUT = 10
    MAX_WORKERS = 3
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    COLOR_SCHEME = {
        "success": "\033[32m",
        "error": "\033[31m",
        "warning": "\033[33m",
        "info": "\033[36m",
        "menu": "\033[35m",
        "reset": "\033[0m"
    }
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    REPORT_DIR = os.path.join(APP_DIR, "reports")
    CACHE_DIR = os.path.join(APP_DIR, "cache")
    LOG_FILE = os.path.join(APP_DIR, "hackload.log")


class Logger:
    def __init__(self, log_file: str = Config.LOG_FILE):
        self.log_file = log_file
        self._ensure_directory_exists(os.path.dirname(log_file))

    def _ensure_directory_exists(self, directory: str):
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except:
                pass

    def log(self, level: str, message: str):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level.upper()}] {message}\n"
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except:
            print(f"Не удалось записать в лог: {log_entry}")

    def info(self, message: str):
        self.log("info", message)

    def warning(self, message: str):
        self.log("warning", message)

    def error(self, message: str):
        self.log("error", message)


class CacheManager:
    def __init__(self, cache_dir: str = Config.CACHE_DIR):
        self.cache_dir = cache_dir
        self._ensure_directory_exists(cache_dir)

    def _ensure_directory_exists(self, directory: str):
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except:
                pass

    def get_cache_key(self, func_name: str, params: Dict) -> str:
        try:
            param_str = json.dumps(params, sort_keys=True)
            return hashlib.md5(f"{func_name}_{param_str}".encode()).hexdigest()
        except:
            return hashlib.md5(f"{func_name}_{str(params)}".encode()).hexdigest()

    def get(self, func_name: str, params: Dict) -> Optional[Dict]:
        try:
            cache_key = self.get_cache_key(func_name, params)
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    cache_time = data.get('timestamp', 0)

                    if isinstance(cache_time, str):
                        try:
                            cache_dt = datetime.fromisoformat(cache_time.replace('Z', '+00:00'))
                            cache_time = cache_dt.timestamp()
                        except:
                            cache_time = 0

                    if time.time() - cache_time < 3600:
                        return data.get('data')
        except:
            pass
        return None

    def set(self, func_name: str, params: Dict, data: Dict):
        try:
            self._ensure_directory_exists(self.cache_dir)
            cache_key = self.get_cache_key(func_name, params)
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'data': data
            }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Не удалось сохранить в кэш: {str(e)}")


class NetworkTools:
    @staticmethod
    def get_headers() -> Dict:
        return {
            'User-Agent': Config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }

    @staticmethod
    def make_request(url: str, method: str = "GET", timeout: int = Config.DEFAULT_TIMEOUT, **kwargs) -> Optional[
        requests.Response]:
        try:
            headers = NetworkTools.get_headers()
            if 'headers' in kwargs:
                headers.update(kwargs.pop('headers'))

            response = requests.request(
                method=method,
                url=url,
                timeout=timeout,
                headers=headers,
                **kwargs
            )
            return response
        except requests.exceptions.Timeout:
            Logger().error(f"Request timeout: {url}")
            return None
        except requests.exceptions.RequestException as e:
            Logger().error(f"Request failed: {url} - {str(e)}")
            return None
        except Exception as e:
            Logger().error(f"Unexpected error in request: {url} - {str(e)}")
            return None


class InputValidator:
    @staticmethod
    def validate_telegram_username(username: str) -> bool:
        if not username:
            return False
        pattern = r'^[a-zA-Z0-9_]{5,32}$'
        return bool(re.match(pattern, username))

    @staticmethod
    def validate_phone_number(phone: str) -> bool:
        if not phone:
            return False
        try:
            parsed = phonenumbers.parse(phone, None)
            return phonenumbers.is_valid_number(parsed)
        except:
            return False

    @staticmethod
    def validate_email(email: str) -> bool:
        if not email:
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    @staticmethod
    def validate_url(url: str) -> bool:
        if not url:
            return False
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    @staticmethod
    def validate_domain(domain: str) -> bool:
        if not domain:
            return False
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$'
        return bool(re.match(pattern, domain))


class Display:
    @staticmethod
    def clear_screen():
        try:
            os.system('cls' if os.name == 'nt' else 'clear')
        except:
            print("\n" * 50)

    @staticmethod
    def print_colored(text: str, color_type: str = "info"):
        color = Config.COLOR_SCHEME.get(color_type, Config.COLOR_SCHEME["info"])
        print(f"{color}{text}{Config.COLOR_SCHEME['reset']}")

    @staticmethod
    def print_banner():
        Display.clear_screen()
        try:
            banner = pyfiglet.figlet_format("HACK LOAD", font="ansi_shadow")
            Display.print_colored(banner, "menu")
        except:
            Display.print_colored("\n" + "=" * 60, "menu")
            Display.print_colored("\n   H A C K   L O A D   v1.0", "menu")
            Display.print_colored("\n" + "=" * 60, "menu")

        menu = "--------------------------------------------------------------------]\n[1]  Telegram\t\t\t[3]  VK\t\t\t[7]  Exit\n[2]  Phone\t\t\t[4]  Photo\n[5]  Settings\t\t\t[6]  Bat file\n"
        Display.print_colored(menu, "menu")

    @staticmethod
    def print_header(title: str):
        print("\n" + "=" * 60)
        Display.print_colored(f" {title} ", "info")
        print("=" * 60)

    @staticmethod
    def print_table(data: List[List[str]], headers: List[str]):
        if not data or not headers:
            return

        try:
            col_widths = [len(str(h)) for h in headers]
            for row in data:
                for i, cell in enumerate(row):
                    if i < len(col_widths):
                        col_widths[i] = max(col_widths[i], len(str(cell)))

            header_line = " | ".join(str(h).ljust(w) for h, w in zip(headers, col_widths))
            separator = "-+-".join("-" * w for w in col_widths)

            print("\n" + header_line)
            print(separator)

            for row in data:
                row_line = " | ".join(str(cell).ljust(w) for cell, w in zip(row[:len(col_widths)], col_widths))
                print(row_line)
        except:
            pass

    @staticmethod
    def loading_animation(message: str, duration: int = 2):
        symbols = ['|', '/', '-', '\\']
        end_time = time.time() + duration
        i = 0

        print(f"\r{message} ", end="")
        while time.time() < end_time:
            print(f"\r{message} {symbols[i % len(symbols)]}", end="", flush=True)
            time.sleep(0.1)
            i += 1
        print("\r" + " " * (len(message) + 2), end="\r")


class TelegramChecker:
    def __init__(self):
        self.cache = CacheManager()
        self.logger = Logger()

    def check(self, username: str) -> Dict[str, Any]:
        cache_key = {'username': username}
        cached = self.cache.get('telegram_check', cache_key)
        if cached:
            return cached

        Display.loading_animation("Анализ Telegram аккаунта")

        result = {
            'username': username,
            'check_date': datetime.now().isoformat(),
            'telegram_exists': False,
            'checks': {}
        }

        try:
            check_functions = [
                self._check_telegram_web,
                self._check_social_mentions,
                self._check_leaks
            ]

            with concurrent.futures.ThreadPoolExecutor(
                    max_workers=min(len(check_functions), Config.MAX_WORKERS)) as executor:
                futures = [executor.submit(func, username) for func in check_functions]

                for future in concurrent.futures.as_completed(futures):
                    try:
                        check_result = future.result(timeout=15)
                        if check_result:
                            result['checks'].update(check_result)
                    except Exception as e:
                        self.logger.error(f"Check failed: {str(e)}")
                        continue

            result['telegram_exists'] = result['checks'].get('telegram_web', {}).get('exists', False)
            self.cache.set('telegram_check', cache_key, result)

        except Exception as e:
            self.logger.error(f"Telegram check error: {str(e)}")
            result['error'] = str(e)

        return result

    def _check_telegram_web(self, username: str) -> Dict:
        check_result = {'telegram_web': {'exists': False}}

        try:
            url = f"https://t.me/{username}"
            response = NetworkTools.make_request(url, timeout=15)

            if response and response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.find('title')

                if title and 'Telegram: Contact' in title.text:
                    check_result['telegram_web']['exists'] = True
                    check_result['telegram_web']['url'] = url

                    name_tag = soup.find('div', class_='tgme_page_title')
                    if name_tag:
                        check_result['telegram_web']['name'] = name_tag.text.strip()

                    bio_tag = soup.find('div', class_='tgme_page_description')
                    if bio_tag:
                        check_result['telegram_web']['bio'] = bio_tag.text.strip()

                    subscribers_tag = soup.find('div', class_='tgme_page_extra')
                    if subscribers_tag:
                        text = subscribers_tag.text.strip()
                        check_result['telegram_web']['subscribers'] = text
                        if 'subscribers' in text.lower() or 'members' in text.lower():
                            check_result['telegram_web']['type'] = 'channel/group'
                        else:
                            check_result['telegram_web']['type'] = 'personal'

                    img_tag = soup.find('img', class_='tgme_page_photo_image')
                    if img_tag and 'src' in img_tag.attrs:
                        check_result['telegram_web']['avatar'] = img_tag['src']

                    phone_pattern = r'[\+\d\s\-\(\)]{10,}'
                    phones = re.findall(phone_pattern, response.text)
                    clean_phones = [p.strip() for p in phones if len(re.sub(r'\D', '', p)) >= 10]
                    if clean_phones:
                        check_result['telegram_web']['possible_phones'] = list(set(clean_phones[:5]))
        except Exception as e:
            self.logger.error(f"Telegram web check failed: {str(e)}")

        return check_result

    def _check_social_mentions(self, username: str) -> Dict:
        check_result = {'social_mentions': {'found': []}}

        social_platforms = {
            'twitter': f'https://twitter.com/{username}',
            'instagram': f'https://www.instagram.com/{username}/',
            'github': f'https://github.com/{username}',
            'vk': f'https://vk.com/{username}',
            'reddit': f'https://reddit.com/user/{username}'
        }

        for platform, url in social_platforms.items():
            try:
                response = NetworkTools.make_request(url, timeout=5)
                if response and response.status_code == 200:
                    check_result['social_mentions']['found'].append({
                        'platform': platform,
                        'url': url,
                        'exists': True
                    })
            except:
                continue

        return check_result

    def _check_leaks(self, username: str) -> Dict:
        check_result = {'leaks': {'found': False}}

        try:
            url = f'https://haveibeenpwned.com/unifiedsearch/{username}'
            response = NetworkTools.make_request(url, timeout=10)

            if response and response.status_code == 200:
                try:
                    data = response.json()
                    if 'Breaches' in data and data['Breaches']:
                        check_result['leaks']['found'] = True
                        check_result['leaks']['count'] = len(data['Breaches'])
                        check_result['leaks']['breaches'] = [
                            {
                                'title': b.get('Title', 'Unknown'),
                                'date': b.get('AddedDate', 'Unknown'),
                                'description': str(b.get('Description', ''))[:100]
                            }
                            for b in data['Breaches'][:3]
                        ]
                except json.JSONDecodeError:
                    pass
        except:
            pass

        return check_result

    def display_results(self, results: Dict):
        Display.print_header("РЕЗУЛЬТАТЫ ПРОВЕРКИ TELEGRAM")

        print(f"\nUsername: @{results.get('username', 'N/A')}")
        print(f"Дата проверки: {results.get('check_date', 'N/A')}")

        if 'error' in results:
            Display.print_colored(f"Ошибка: {results['error']}", "error")
            return

        exists = results.get('telegram_exists', False)
        print(f"Статус: {'Найден' if exists else 'Не найден'}")

        web_info = results.get('checks', {}).get('telegram_web', {})
        if web_info.get('exists'):
            print(f"\nИнформация с t.me:")
            if 'name' in web_info:
                print(f"  Имя: {web_info['name']}")
            if 'type' in web_info:
                print(f"  Тип: {web_info['type']}")
            if 'bio' in web_info:
                print(f"  Описание: {web_info['bio']}")
            if 'subscribers' in web_info:
                print(f"  Подписчики: {web_info['subscribers']}")
            if 'avatar' in web_info:
                print(f"  Аватар: {web_info['avatar']}")
            if 'possible_phones' in web_info:
                print(f"\n  Возможные телефоны:")
                for phone in web_info['possible_phones']:
                    print(f"    - {phone}")

        social_info = results.get('checks', {}).get('social_mentions', {}).get('found', [])
        if social_info:
            print(f"\nУпоминания в социальных сетях:")
            for item in social_info:
                print(f"  - {item['platform']}: {'Найден' if item.get('exists') else 'Не найден'}")

        leaks_info = results.get('checks', {}).get('leaks', {})
        if leaks_info.get('found'):
            print(f"\nУтечки данных: {leaks_info.get('count', 0)} инцидентов")
            for breach in leaks_info.get('breaches', []):
                print(f"  - {breach.get('title')} ({breach.get('date')})")

        print("\n" + "=" * 60)


class PhoneChecker:
    def __init__(self):
        self.cache = CacheManager()
        self.logger = Logger()

    def check(self, phone_number: str) -> Dict[str, Any]:
        cache_key = {'phone': phone_number}
        cached = self.cache.get('phone_check', cache_key)
        if cached:
            return cached

        Display.loading_animation("Анализ номера телефона")

        result = {
            'phone_number': phone_number,
            'check_date': datetime.now().isoformat(),
            'valid': False,
            'details': {}
        }

        try:
            parsed = phonenumbers.parse(phone_number, None)
            result['valid'] = phonenumbers.is_valid_number(parsed)

            if result['valid']:
                result['details']['country'] = geocoder.description_for_number(parsed, "en")
                result['details']['operator'] = carrier.name_for_number(parsed, "en") or "Unknown"
                result['details']['timezone'] = timezone.time_zones_for_number(parsed)
                result['details']['format_international'] = phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )
                result['details']['format_national'] = phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.NATIONAL
                )
                result['details']['country_code'] = parsed.country_code
                result['details']['national_number'] = parsed.national_number

                try:
                    region = geocoder.description_for_number(parsed, "en", region=True)
                    if region:
                        result['details']['region'] = region
                except:
                    pass
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"Phone check error: {str(e)}")

        self.cache.set('phone_check', cache_key, result)
        return result

    def display_results(self, results: Dict):
        Display.print_header("РЕЗУЛЬТАТЫ ПРОВЕРКИ ТЕЛЕФОНА")

        print(f"\nНомер телефона: {results.get('phone_number', 'N/A')}")
        print(f"Дата проверки: {results.get('check_date', 'N/A')}")

        if 'error' in results:
            Display.print_colored(f"Ошибка: {results['error']}", "error")
            return

        print(f"Валидность: {'Да' if results.get('valid') else 'Нет'}")

        if results.get('valid'):
            details = results.get('details', {})
            print(f"\nИнформация о номере:")
            print(f"  Страна: {details.get('country', 'Неизвестно')}")
            print(f"  Оператор: {details.get('operator', 'Неизвестно')}")

            timezones = details.get('timezone', [])
            if timezones:
                print(f"  Часовой пояс: {', '.join(timezones)}")

            print(f"  Международный формат: {details.get('format_international', 'Неизвестно')}")
            print(f"  Национальный формат: {details.get('format_national', 'Неизвестно')}")
            print(f"  Код страны: +{details.get('country_code', 'Неизвестно')}")

            if 'region' in details:
                print(f"  Регион: {details['region']}")

        print("\n" + "=" * 60)


class PhotoAnalyzer:
    def __init__(self):
        self.supported_formats = ['.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.webp', '.gif']

    def analyze(self, image_path: str) -> Dict[str, Any]:
        result = {
            'image_path': image_path,
            'check_date': datetime.now().isoformat(),
            'file_info': {},
            'exif_data': {},
            'analysis': {}
        }

        if not os.path.exists(image_path):
            result['error'] = 'Файл не найден'
            return result

        try:
            file_ext = os.path.splitext(image_path)[1].lower()
            if file_ext not in self.supported_formats:
                result['error'] = f'Неподдерживаемый формат изображения: {file_ext}'
                return result

            Display.loading_animation("Анализ изображения")

            with Image.open(image_path) as img:
                result['file_info'] = {
                    'format': img.format or 'Unknown',
                    'mode': img.mode,
                    'size': img.size,
                    'width': img.width,
                    'height': img.height,
                    'filesize': os.path.getsize(image_path),
                    'filename': os.path.basename(image_path)
                }

                try:
                    result['file_info']['md5'] = self._calculate_hash(image_path, 'md5')
                    result['file_info']['sha256'] = self._calculate_hash(image_path, 'sha256')
                except:
                    pass

                exif = self._extract_exif(img)
                if exif:
                    result['exif_data'] = exif

                result['analysis'] = {
                    'has_gps': 'GPSInfo' in exif,
                    'has_metadata': len(exif) > 0,
                    'color_analysis': self._analyze_colors(img),
                    'security_issues': self._check_security_issues(exif)
                }

        except Exception as e:
            result['error'] = str(e)

        return result

    def _extract_exif(self, image: Image) -> Dict:
        exif_data = {}

        try:
            if hasattr(image, '_getexif') and image._getexif():
                exif = image._getexif()
                if exif:
                    for tag_id, value in exif.items():
                        tag = TAGS.get(tag_id, tag_id)

                        try:
                            if isinstance(value, bytes):
                                value = value.decode('utf-8', errors='ignore')
                            elif isinstance(value, (int, float)):
                                value = str(value)

                            exif_data[tag] = value
                        except:
                            exif_data[tag] = str(value)
        except:
            pass

        return exif_data

    def _calculate_hash(self, filepath: str, algorithm: str) -> str:
        hash_func = getattr(hashlib, algorithm)()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        return hash_func.hexdigest()

    def _analyze_colors(self, image: Image) -> Dict:
        analysis = {}

        try:
            if image.mode not in ['RGB', 'RGBA']:
                image = image.convert('RGB')

            pixels = list(image.getdata())[:5000]
            total_pixels = len(pixels)

            if total_pixels == 0:
                return analysis

            color_counts = {}
            for pixel in pixels:
                color_counts[pixel] = color_counts.get(pixel, 0) + 1

            top_colors = sorted(color_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            analysis['top_colors'] = [
                {
                    'rgb': str(color[:3]),
                    'count': count,
                    'percentage': round((count / total_pixels) * 100, 2)
                }
                for color, count in top_colors
            ]

            analysis['unique_colors'] = len(color_counts)
            analysis['sample_size'] = total_pixels

        except Exception as e:
            analysis['error'] = str(e)

        return analysis

    def _check_security_issues(self, exif_data: Dict) -> List[str]:
        issues = []

        sensitive_tags = [
            'GPSInfo', 'Make', 'Model', 'SerialNumber', 'Software',
            'DateTimeOriginal', 'Artist', 'Copyright', 'HostComputer'
        ]

        for tag in sensitive_tags:
            if tag in exif_data:
                value = exif_data[tag]
                if value and str(value).strip():
                    issues.append(f"Обнаружен тег {tag}: {value}")

        return issues

    def display_results(self, results: Dict):
        Display.print_header("РЕЗУЛЬТАТЫ АНАЛИЗА ИЗОБРАЖЕНИЯ")

        if 'error' in results:
            Display.print_colored(f"Ошибка: {results['error']}", "error")
            return

        file_info = results.get('file_info', {})
        print(f"\nФайл: {file_info.get('filename', 'N/A')}")
        print(f"Дата анализа: {results.get('check_date', 'N/A')}")

        print(f"\nОсновная информация:")
        print(f"  Размер: {file_info.get('width', 0)}x{file_info.get('height', 0)}")
        print(f"  Формат: {file_info.get('format', 'Unknown')}")
        print(f"  Режим цвета: {file_info.get('mode', 'Unknown')}")

        filesize = file_info.get('filesize', 0)
        if filesize >= 1024 * 1024:
            print(f"  Размер файла: {filesize / (1024 * 1024):.2f} MB")
        else:
            print(f"  Размер файла: {filesize / 1024:.2f} KB")

        if 'md5' in file_info:
            print(f"  MD5: {file_info['md5']}")

        exif_data = results.get('exif_data', {})
        if exif_data:
            print(f"\nEXIF метаданные:")
            important_tags = ['Make', 'Model', 'DateTime', 'Software', 'Artist', 'Copyright']
            for tag in important_tags:
                if tag in exif_data:
                    print(f"  {tag}: {exif_data[tag]}")

        analysis = results.get('analysis', {})
        if analysis.get('color_analysis'):
            colors = analysis['color_analysis'].get('top_colors', [])[:3]
            if colors:
                print(f"\nЦветовая палитра (топ-3):")
                for color_info in colors:
                    print(f"  {color_info['rgb']}: {color_info['percentage']}%")

        if analysis.get('security_issues'):
            print(f"\nПроблемы безопасности:")
            for issue in analysis['security_issues']:
                print(f"  • {issue}")

        print(f"\nРекомендации:")
        print("  1. Удалите EXIF данные перед публикацией")
        print("  2. Проверьте изображение через обратный поиск")
        print("  3. Избегайте публикации фото с личной информацией")

        print("\n" + "=" * 60)

    def clean_exif(self, image_path: str, output_path: str = None) -> bool:
        try:
            if not os.path.exists(image_path):
                return False

            with Image.open(image_path) as img:
                data = list(img.getdata())

                if img.mode in ['P', 'PA']:
                    new_img = Image.new('RGBA', img.size)
                else:
                    new_img = Image.new(img.mode, img.size)

                new_img.putdata(data)

                if output_path is None:
                    filename, ext = os.path.splitext(image_path)
                    output_path = f"{filename}_cleaned{ext}"

                new_img.save(output_path)
                return True

        except Exception as e:
            self.logger.error(f"Failed to clean EXIF: {str(e)}")
            return False


class DomainChecker:
    def __init__(self):
        self.cache = CacheManager()
        self.logger = Logger()

    def check(self, domain: str) -> Dict[str, Any]:
        cache_key = {'domain': domain}
        cached = self.cache.get('domain_check', cache_key)
        if cached:
            return cached

        Display.loading_animation("Анализ домена")

        result = {
            'domain': domain,
            'check_date': datetime.now().isoformat(),
            'checks': {}
        }

        try:
            check_functions = [
                self._check_dns,
                self._check_http,
                self._check_subdomains
            ]

            with concurrent.futures.ThreadPoolExecutor(
                    max_workers=min(len(check_functions), Config.MAX_WORKERS)) as executor:
                futures = [executor.submit(func, domain) for func in check_functions]

                for future in concurrent.futures.as_completed(futures):
                    try:
                        check_type = check_functions[futures.index(future)].__name__.replace('_check_', '')
                        check_result = future.result(timeout=15)
                        result['checks'][check_type] = check_result
                    except Exception as e:
                        self.logger.error(f"Domain check failed: {str(e)}")
                        continue

        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"Domain check error: {str(e)}")

        self.cache.set('domain_check', cache_key, result)
        return result

    def _check_dns(self, domain: str) -> Dict:
        dns_info = {'records': {}}

        record_types = ['A', 'AAAA', 'MX', 'NS', 'TXT', 'CNAME']

        for record_type in record_types:
            try:
                import dns.resolver
                answers = dns.resolver.resolve(domain, record_type)
                dns_info['records'][record_type] = [str(r) for r in answers]
            except:
                continue

        return dns_info

    def _check_http(self, domain: str) -> Dict:
        http_info = {}

        try:
            if not domain.startswith(('http://', 'https://')):
                url = f"http://{domain}"
            else:
                url = domain

            response = NetworkTools.make_request(url, timeout=10)

            if response:
                http_info['status_code'] = response.status_code
                http_info['server'] = response.headers.get('Server', 'Неизвестно')
                http_info['content_type'] = response.headers.get('Content-Type', 'Неизвестно')
                http_info['content_length'] = response.headers.get('Content-Length', 'Неизвестно')

                try:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    if soup.title:
                        http_info['title'] = soup.title.string.strip()
                except:
                    pass
        except Exception as e:
            http_info['error'] = str(e)

        return http_info

    def _check_subdomains(self, domain: str) -> Dict:
        subdomains_info = {'found': []}

        common_subdomains = [
            'www', 'mail', 'ftp', 'blog', 'shop', 'admin',
            'test', 'dev', 'api', 'cdn', 'static', 'mobile'
        ]

        for sub in common_subdomains:
            subdomain = f"{sub}.{domain}"
            try:
                socket.gethostbyname(subdomain)
                subdomains_info['found'].append(subdomain)
            except socket.gaierror:
                continue
            except:
                break

        return subdomains_info

    def display_results(self, results: Dict):
        Display.print_header("РЕЗУЛЬТАТЫ ПРОВЕРКИ ДОМЕНА")

        print(f"\nДомен: {results.get('domain', 'N/A')}")
        print(f"Дата проверки: {results.get('check_date', 'N/A')}")

        if 'error' in results:
            Display.print_colored(f"Ошибка: {results['error']}", "error")
            return

        checks = results.get('checks', {})

        if 'dns' in checks:
            dns_info = checks['dns']
            records = dns_info.get('records', {})
            if records:
                print(f"\nDNS записи:")
                for record_type, values in records.items():
                    if values:
                        print(f"  {record_type}: {', '.join(values[:3])}")

        if 'http' in checks:
            http_info = checks['http']
            if 'error' not in http_info:
                print(f"\nHTTP информация:")
                print(f"  Статус код: {http_info.get('status_code', 'Неизвестно')}")
                print(f"  Сервер: {http_info.get('server', 'Неизвестно')}")
                if 'title' in http_info:
                    print(f"  Заголовок: {http_info['title']}")

        if 'subdomains' in checks:
            subdomains_info = checks['subdomains']
            found = subdomains_info.get('found', [])
            if found:
                print(f"\nНайденные поддомены:")
                for subdomain in found[:5]:
                    print(f"  - {subdomain}")
                if len(found) > 5:
                    print(f"  ... и еще {len(found) - 5}")

        print("\n" + "=" * 60)


class ReportGenerator:
    def __init__(self):
        self.report_dir = Config.REPORT_DIR
        self._ensure_directory_exists(self.report_dir)

    def _ensure_directory_exists(self, directory: str):
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception as e:
                print(f"Не удалось создать папку {directory}: {str(e)}")
                self.report_dir = tempfile.gettempdir()

    def generate(self, data: Dict, report_type: str = 'txt', filename: str = None) -> str:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if not filename:
            filename = f"report_{timestamp}"

        try:
            safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            filepath = os.path.join(self.report_dir, f"{safe_filename}.{report_type}")

            if report_type == 'txt':
                self._generate_txt_report(data, filepath)
            elif report_type == 'json':
                self._generate_json_report(data, filepath)
            elif report_type == 'csv':
                self._generate_csv_report(data, filepath)
            else:
                filepath = self._generate_txt_report(data, filepath)

            return filepath
        except Exception as e:
            print(f"Ошибка при генерации отчета: {str(e)}")
            return ""

    def _generate_txt_report(self, data: Dict, filepath: str) -> str:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("HACK LOAD - ОТЧЕТ\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Дата создания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Тип проверки: {data.get('check_type', 'Unknown')}\n")
                f.write("-" * 80 + "\n\n")

                self._write_dict(f, data, 0)
            return filepath
        except Exception as e:
            print(f"Ошибка при создании TXT отчета: {str(e)}")
            return ""

    def _write_dict(self, file, data, indent):
        try:
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, dict):
                        file.write(" " * indent + f"{key}:\n")
                        self._write_dict(file, value, indent + 2)
                    elif isinstance(value, list):
                        file.write(" " * indent + f"{key}:\n")
                        for item in value:
                            if isinstance(item, dict):
                                self._write_dict(file, item, indent + 4)
                            else:
                                file.write(" " * (indent + 2) + f"- {item}\n")
                    else:
                        file.write(" " * indent + f"{key}: {value}\n")
        except:
            pass

    def _generate_json_report(self, data: Dict, filepath: str) -> str:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return filepath
        except Exception as e:
            print(f"Ошибка при создании JSON отчета: {str(e)}")
            return ""

    def _generate_csv_report(self, data: Dict, filepath: str) -> str:
        try:
            flattened = self._flatten_dict(data)

            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Key', 'Value'])
                for key, value in flattened.items():
                    if isinstance(value, (list, dict)):
                        value = str(value)
                    writer.writerow([key, value])
            return filepath
        except Exception as e:
            print(f"Ошибка при создании CSV отчета: {str(e)}")
            return ""

    def _flatten_dict(self, d, parent_key='', sep='.'):
        items = []
        try:
            for k, v in d.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(self._flatten_dict(v, new_key, sep=sep).items())
                elif isinstance(v, list):
                    items.append((new_key, '; '.join(map(str, v))))
                else:
                    items.append((new_key, v))
        except:
            pass
        return dict(items)


class SettingsManager:
    def __init__(self):
        self.settings_file = os.path.join(Config.APP_DIR, 'hackload_settings.json')
        self.settings = self._load_settings()

    def _load_settings(self) -> Dict:
        default_settings = {
            'general': {
                'language': 'ru',
                'auto_save': True,
                'timeout': Config.DEFAULT_TIMEOUT,
                'max_workers': Config.MAX_WORKERS,
                'color_scheme': 'default'
            },
            'network': {
                'use_proxy': False,
                'proxy_address': '',
                'verify_ssl': True,
                'user_agent': Config.USER_AGENT
            },
            'reports': {
                'default_format': 'txt',
                'save_location': Config.REPORT_DIR,
                'include_timestamp': True
            }
        }

        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    for section in default_settings:
                        if section in loaded:
                            default_settings[section].update(loaded[section])
        except:
            pass

        return default_settings

    def save_settings(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка при сохранении настроек: {str(e)}")
            return False

    def get(self, section: str, key: str, default=None):
        return self.settings.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value):
        if section not in self.settings:
            self.settings[section] = {}
        self.settings[section][key] = value


class NetworkToolsModule:
    @staticmethod
    def port_scan(host: str, ports: List[int] = None) -> Dict:
        if ports is None:
            ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 465, 587, 993, 995, 3306, 3389, 5432, 8080]

        open_ports = []

        print(f"\nСканирование портов {host}...")

        for port in ports[:20]:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                if result == 0:
                    open_ports.append(port)
                sock.close()
            except:
                continue

        return {
            'host': host,
            'total_scanned': len(ports[:20]),
            'open_ports': open_ports,
            'scan_time': datetime.now().isoformat()
        }

    @staticmethod
    def ping_host(host: str) -> Dict:
        result = {'host': host, 'success': False}

        param = '-n' if platform.system().lower() == 'windows' else '-c'
        count = '3'

        try:
            if platform.system().lower() == 'windows':
                command = ['ping', param, count, '-w', '3000', host]
            else:
                command = ['ping', param, count, '-W', '3', host]

            output = subprocess.check_output(command, universal_newlines=True, stderr=subprocess.DEVNULL)
            result['success'] = True
            result['output'] = output

            lines = output.split('\n')
            for line in lines:
                if 'time=' in line or 'time<' in line:
                    result['response_time'] = line
                    break

        except subprocess.CalledProcessError:
            result['success'] = False
            result['output'] = 'Host unreachable'
        except Exception as e:
            result['success'] = False
            result['output'] = f'Error: {str(e)}'

        return result


class HackLoad:
    def __init__(self):
        self.settings = SettingsManager()
        self.logger = Logger()
        self.report_generator = ReportGenerator()
        self.running = True
        self.current_module = None

        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, signum, frame):
        print("\n\nПолучен сигнал прерывания...")
        self.running = False
        sys.exit(0)

    def run(self):
        while self.running:
            try:
                Display.print_banner()
                choice = input("\nHACKLOAD> ").strip()

                if choice == '1':
                    self.telegram_module()
                elif choice == '2':
                    self.phone_module()
                elif choice == '3':
                    self.photo_module()
                elif choice == '4':
                    self.domain_module()
                elif choice == '5':
                    self.network_module()
                elif choice == '6':
                    self.settings_module()
                elif choice == '7':
                    self.reports_module()
                elif choice == '0':
                    self.exit_program()
                else:
                    Display.print_colored("Неверный выбор. Попробуйте снова.", "error")
                    time.sleep(1)
            except KeyboardInterrupt:
                continue
            except Exception as e:
                self.logger.error(f"Error in main loop: {str(e)}")
                Display.print_colored(f"Ошибка: {str(e)}", "error")
                time.sleep(2)

    def telegram_module(self):
        self.current_module = 'telegram'
        Display.clear_screen()
        Display.print_header("TELEGRAM CHECKER")

        username = input("\nВведите Telegram username (без @): ").strip()

        if not username:
            Display.print_colored("Имя пользователя не может быть пустым", "error")
            time.sleep(2)
            return

        if not InputValidator.validate_telegram_username(username):
            Display.print_colored("Неверный формат имени пользователя (5-32 символов, буквы, цифры, _)", "error")
            time.sleep(2)
            return

        checker = TelegramChecker()
        results = checker.check(username)
        checker.display_results(results)

        if self.settings.get('reports', 'auto_save', False):
            try:
                report_file = self.report_generator.generate(
                    results,
                    self.settings.get('reports', 'default_format', 'txt'),
                    f"telegram_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                if report_file:
                    Display.print_colored(f"\nОтчет сохранен: {report_file}", "success")
            except Exception as e:
                Display.print_colored(f"\nОшибка при сохранении отчета: {str(e)}", "error")

        input("\nНажмите Enter для продолжения...")

    def phone_module(self):
        self.current_module = 'phone'
        Display.clear_screen()
        Display.print_header("PHONE CHECKER")

        phone = input("\nВведите номер телефона (с кодом страны, например +79123456789): ").strip()

        if not phone:
            Display.print_colored("Номер телефона не может быть пустым", "error")
            time.sleep(2)
            return

        if not InputValidator.validate_phone_number(phone):
            Display.print_colored("Неверный формат номера телефона", "error")
            time.sleep(2)
            return

        checker = PhoneChecker()
        results = checker.check(phone)
        checker.display_results(results)

        if self.settings.get('reports', 'auto_save', False):
            try:
                safe_phone = re.sub(r'[^0-9]', '', phone)
                report_file = self.report_generator.generate(
                    results,
                    self.settings.get('reports', 'default_format', 'txt'),
                    f"phone_{safe_phone}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                if report_file:
                    Display.print_colored(f"\nОтчет сохранен: {report_file}", "success")
            except Exception as e:
                Display.print_colored(f"\nОшибка при сохранении отчета: {str(e)}", "error")

        input("\nНажмите Enter для продолжения...")

    def photo_module(self):
        self.current_module = 'photo'

        while True:
            Display.clear_screen()
            Display.print_header("PHOTO ANALYZER")

            print("\n1. Анализ метаданных")
            print("2. Очистка EXIF данных")
            print("0. Назад")

            sub_choice = input("\nВыберите опцию: ").strip()

            if sub_choice == '0':
                break
            elif sub_choice == '1':
                self._analyze_photo()
            elif sub_choice == '2':
                self._clean_photo_exif()
            else:
                Display.print_colored("Неверный выбор", "error")
                time.sleep(1)

    def _analyze_photo(self):
        image_path = input("\nВведите путь к изображению: ").strip()

        if not image_path:
            Display.print_colored("Путь не может быть пустым", "error")
            time.sleep(2)
            return

        if not os.path.exists(image_path):
            Display.print_colored("Файл не найден", "error")
            time.sleep(2)
            return

        analyzer = PhotoAnalyzer()
        results = analyzer.analyze(image_path)
        analyzer.display_results(results)

        if self.settings.get('reports', 'auto_save', False):
            try:
                filename = os.path.basename(image_path)
                safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
                report_file = self.report_generator.generate(
                    results,
                    self.settings.get('reports', 'default_format', 'txt'),
                    f"photo_{safe_filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                if report_file:
                    Display.print_colored(f"\nОтчет сохранен: {report_file}", "success")
            except Exception as e:
                Display.print_colored(f"\nОшибка при сохранении отчета: {str(e)}", "error")

        input("\nНажмите Enter для продолжения...")

    def _clean_photo_exif(self):
        image_path = input("\nВведите путь к изображению: ").strip()

        if not image_path:
            Display.print_colored("Путь не может быть пустым", "error")
            time.sleep(2)
            return

        if not os.path.exists(image_path):
            Display.print_colored("Файл не найден", "error")
            time.sleep(2)
            return

        output_path = input("Введите путь для сохранения (оставьте пустым для auto): ").strip()

        analyzer = PhotoAnalyzer()
        success = analyzer.clean_exif(image_path, output_path if output_path else None)

        if success:
            Display.print_colored("EXIF данные успешно удалены", "success")
        else:
            Display.print_colored("Не удалось удалить EXIF данные", "error")

        input("\nНажмите Enter для продолжения...")

    def domain_module(self):
        self.current_module = 'domain'
        Display.clear_screen()
        Display.print_header("DOMAIN CHECKER")

        domain = input("\nВведите домен (например: example.com): ").strip()

        if not domain:
            Display.print_colored("Домен не может быть пустым", "error")
            time.sleep(2)
            return

        if not InputValidator.validate_domain(domain):
            Display.print_colored("Неверный формат домена", "error")
            time.sleep(2)
            return

        checker = DomainChecker()
        results = checker.check(domain)
        checker.display_results(results)

        if self.settings.get('reports', 'auto_save', False):
            try:
                report_file = self.report_generator.generate(
                    results,
                    self.settings.get('reports', 'default_format', 'txt'),
                    f"domain_{domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                if report_file:
                    Display.print_colored(f"\nОтчет сохранен: {report_file}", "success")
            except Exception as e:
                Display.print_colored(f"\nОшибка при сохранении отчета: {str(e)}", "error")

        input("\nНажмите Enter для продолжения...")

    def network_module(self):
        self.current_module = 'network'

        while True:
            Display.clear_screen()
            Display.print_header("NETWORK TOOLS")

            print("\n1. Проверка портов")
            print("2. Ping хост")
            print("0. Назад")

            sub_choice = input("\nВыберите инструмент: ").strip()

            if sub_choice == '0':
                break
            elif sub_choice == '1':
                self._port_scan_tool()
            elif sub_choice == '2':
                self._ping_tool()
            else:
                Display.print_colored("Неверный выбор", "error")
                time.sleep(1)

    def _port_scan_tool(self):
        host = input("Введите хост или IP адрес: ").strip()

        if not host:
            Display.print_colored("Хост не может быть пустым", "error")
            time.sleep(2)
            return

        custom_ports = input("Введите порты через запятую (оставьте пустым для стандартных): ").strip()

        ports = None
        if custom_ports:
            try:
                ports = [int(p.strip()) for p in custom_ports.split(',') if p.strip().isdigit()]
                ports = [p for p in ports if 1 <= p <= 65535]
            except:
                Display.print_colored("Неверный формат портов", "error")
                time.sleep(2)
                return

        results = NetworkToolsModule.port_scan(host, ports)

        print(f"\nРезультаты сканирования {host}:")
        print(f"Проверено портов: {results.get('total_scanned', 0)}")

        open_ports = results.get('open_ports', [])
        if open_ports:
            print(f"Открытые порты: {', '.join(map(str, open_ports))}")
        else:
            print("Открытых портов не найдено")

        input("\nНажмите Enter для продолжения...")

    def _ping_tool(self):
        host = input("Введите хост или IP адрес: ").strip()

        if not host:
            Display.print_colored("Хост не может быть пустым", "error")
            time.sleep(2)
            return

        results = NetworkToolsModule.ping_host(host)

        print(f"\nРезультаты ping {host}:")
        print(f"Статус: {'Доступен' if results.get('success') else 'Недоступен'}")

        if results.get('response_time'):
            print(f"Время отклика: {results.get('response_time')}")

        input("\nНажмите Enter для продолжения...")

    def settings_module(self):
        self.current_module = 'settings'

        while True:
            Display.clear_screen()
            Display.print_header("НАСТРОЙКИ")

            print("\n1. Общие настройки")
            print("2. Настройки сети")
            print("3. Настройки отчетов")
            print("4. Сброс настроек")
            print("0. Назад")

            choice = input("\nВыберите раздел: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self._general_settings()
            elif choice == '2':
                self._network_settings()
            elif choice == '3':
                self._report_settings()
            elif choice == '4':
                self._reset_settings()
            else:
                Display.print_colored("Неверный выбор", "error")
                time.sleep(1)

    def _general_settings(self):
        while True:
            Display.clear_screen()
            Display.print_header("ОБЩИЕ НАСТРОЙКИ")

            print(f"\nТекущие настройки:")
            print(f"1. Язык: {self.settings.get('general', 'language')}")
            print(f"2. Автосохранение: {'Включено' if self.settings.get('general', 'auto_save') else 'Выключено'}")
            print(f"3. Таймаут: {self.settings.get('general', 'timeout')} сек")
            print(f"4. Максимум потоков: {self.settings.get('general', 'max_workers')}")
            print(f"0. Назад")

            choice = input("\nВыберите настройку: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                lang = input("Язык (ru/en): ").strip().lower()
                if lang in ['ru', 'en']:
                    self.settings.set('general', 'language', lang)
                    self.settings.save_settings()
                    Display.print_colored("Язык изменен", "success")
                else:
                    Display.print_colored("Доступные языки: ru, en", "error")
                time.sleep(1)
            elif choice == '2':
                current = self.settings.get('general', 'auto_save')
                self.settings.set('general', 'auto_save', not current)
                self.settings.save_settings()
                status = "включено" if not current else "выключено"
                Display.print_colored(f"Автосохранение {status}", "success")
                time.sleep(1)
            elif choice == '3':
                try:
                    timeout = int(input("Таймаут (5-30): ").strip())
                    if 5 <= timeout <= 30:
                        self.settings.set('general', 'timeout', timeout)
                        self.settings.save_settings()
                        Display.print_colored("Таймаут изменен", "success")
                    else:
                        Display.print_colored("Таймаут должен быть от 5 до 30 секунд", "error")
                except ValueError:
                    Display.print_colored("Введите число", "error")
                time.sleep(1)
            elif choice == '4':
                try:
                    workers = int(input("Максимум потоков (1-10): ").strip())
                    if 1 <= workers <= 10:
                        self.settings.set('general', 'max_workers', workers)
                        self.settings.save_settings()
                        Display.print_colored("Количество потоков изменено", "success")
                    else:
                        Display.print_colored("Количество потоков должно быть от 1 до 10", "error")
                except ValueError:
                    Display.print_colored("Введите число", "error")
                time.sleep(1)
            else:
                Display.print_colored("Неверный выбор", "error")
                time.sleep(1)

    def _network_settings(self):
        while True:
            Display.clear_screen()
            Display.print_header("НАСТРОЙКИ СЕТИ")

            print(f"\nТекущие настройки:")
            print(f"1. Использовать прокси: {'Да' if self.settings.get('network', 'use_proxy') else 'Нет'}")
            print(f"2. Адрес прокси: {self.settings.get('network', 'proxy_address')}")
            print(f"3. Проверять SSL: {'Да' if self.settings.get('network', 'verify_ssl') else 'Нет'}")
            print(f"0. Назад")

            choice = input("\nВыберите настройку: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                current = self.settings.get('network', 'use_proxy')
                self.settings.set('network', 'use_proxy', not current)
                self.settings.save_settings()
                status = "включено" if not current else "выключено"
                Display.print_colored(f"Использование прокси {status}", "success")
                time.sleep(1)
            elif choice == '2':
                proxy = input("Адрес прокси (формат: http://ip:port): ").strip()
                self.settings.set('network', 'proxy_address', proxy)
                self.settings.save_settings()
                Display.print_colored("Адрес прокси сохранен", "success")
                time.sleep(1)
            elif choice == '3':
                current = self.settings.get('network', 'verify_ssl')
                self.settings.set('network', 'verify_ssl', not current)
                self.settings.save_settings()
                status = "включена" if not current else "выключена"
                Display.print_colored(f"Проверка SSL {status}", "success")
                time.sleep(1)
            else:
                Display.print_colored("Неверный выбор", "error")
                time.sleep(1)

    def _report_settings(self):
        while True:
            Display.clear_screen()
            Display.print_header("НАСТРОЙКИ ОТЧЕТОВ")

            print(f"\nТекущие настройки:")
            print(f"1. Формат по умолчанию: {self.settings.get('reports', 'default_format')}")
            print(f"2. Папка для отчетов: {self.settings.get('reports', 'save_location')}")
            print(
                f"3. Включать дату в имя файла: {'Да' if self.settings.get('reports', 'include_timestamp') else 'Нет'}")
            print(f"0. Назад")

            choice = input("\nВыберите настройку: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                fmt = input("Формат (txt/json/csv): ").strip().lower()
                if fmt in ['txt', 'json', 'csv']:
                    self.settings.set('reports', 'default_format', fmt)
                    self.settings.save_settings()
                    Display.print_colored("Формат отчетов изменен", "success")
                else:
                    Display.print_colored("Доступные форматы: txt, json, csv", "error")
                time.sleep(1)
            elif choice == '2':
                path = input("Путь к папке: ").strip()
                if path:
                    try:
                        os.makedirs(path, exist_ok=True)
                        self.settings.set('reports', 'save_location', path)
                        self.settings.save_settings()
                        Display.print_colored("Папка для отчетов изменена", "success")
                    except Exception as e:
                        Display.print_colored(f"Ошибка: {str(e)}", "error")
                time.sleep(1)
            elif choice == '3':
                current = self.settings.get('reports', 'include_timestamp')
                self.settings.set('reports', 'include_timestamp', not current)
                self.settings.save_settings()
                status = "включено" if not current else "выключено"
                Display.print_colored(f"Включение даты в имя файла {status}", "success")
                time.sleep(1)
            else:
                Display.print_colored("Неверный выбор", "error")
                time.sleep(1)

    def _reset_settings(self):
        confirm = input("\nВы уверены, что хотите сбросить все настройки? (y/n): ").lower()
        if confirm == 'y':
            try:
                if os.path.exists(self.settings.settings_file):
                    os.remove(self.settings.settings_file)
                self.settings = SettingsManager()
                Display.print_colored("Настройки сброшены к значениям по умолчанию", "success")
            except Exception as e:
                Display.print_colored(f"Ошибка: {str(e)}", "error")
            time.sleep(2)

    def reports_module(self):
        self.current_module = 'reports'

        while True:
            Display.clear_screen()
            Display.print_header("ОТЧЕТЫ И ЭКСПОРТ")

            print("\n1. Просмотр последних отчетов")
            print("2. Удалить все отчеты")
            print("3. Открыть папку отчетов")
            print("0. Назад")

            choice = input("\nВыберите опцию: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self._view_reports()
            elif choice == '2':
                self._delete_reports()
            elif choice == '3':
                self._open_reports_folder()
            else:
                Display.print_colored("Неверный выбор", "error")
                time.sleep(1)

    def _view_reports(self):
        report_dir = self.settings.get('reports', 'save_location', Config.REPORT_DIR)

        if not os.path.exists(report_dir):
            print(f"\nПапка отчетов не найдена: {report_dir}")
            input("\nНажмите Enter для продолжения...")
            return

        try:
            reports = []
            for file in os.listdir(report_dir):
                if file.endswith(('.txt', '.json', '.csv')):
                    filepath = os.path.join(report_dir, file)
                    try:
                        stats = os.stat(filepath)
                        reports.append({
                            'name': file,
                            'size': stats.st_size,
                            'modified': datetime.fromtimestamp(stats.st_mtime)
                        })
                    except:
                        continue

            if not reports:
                print("\nОтчетов не найдено")
                input("\nНажмите Enter для продолжения...")
                return

            reports.sort(key=lambda x: x['modified'], reverse=True)

            print(f"\nНайдено отчетов: {len(reports)}")
            print("\nПоследние 10 отчетов:")
            print("-" * 80)
            print(f"{'Файл':<40} {'Размер':<10} {'Дата изменения':<20}")
            print("-" * 80)

            for report in reports[:10]:
                size_kb = report['size'] / 1024
                date_str = report['modified'].strftime('%Y-%m-%d %H:%M')
                print(f"{report['name'][:40]:<40} {size_kb:.1f} KB{'':<5} {date_str:<20}")

            print("-" * 80)

            view = input("\nПросмотреть отчет? (введите номер 1-10 или Enter для пропуска): ").strip()
            if view and view.isdigit():
                index = int(view) - 1
                if 0 <= index < len(reports[:10]):
                    selected = reports[index]
                    filepath = os.path.join(report_dir, selected['name'])
                    if os.path.exists(filepath):
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                content = f.read()
                                print(f"\n{'-' * 80}")
                                print(content[:1000])
                                if len(content) > 1000:
                                    print("... (содержимое обрезано)")
                                print(f"{'-' * 80}")
                        except:
                            print("Не удалось прочитать файл")
        except Exception as e:
            Display.print_colored(f"Ошибка: {str(e)}", "error")

        input("\nНажмите Enter для продолжения...")

    def _delete_reports(self):
        confirm = input("\nВы уверены, что хотите удалить все отчеты? (y/n): ").lower()
        if confirm == 'y':
            report_dir = self.settings.get('reports', 'save_location', Config.REPORT_DIR)

            if os.path.exists(report_dir):
                try:
                    deleted_count = 0
                    for file in os.listdir(report_dir):
                        if file.endswith(('.txt', '.json', '.csv')):
                            filepath = os.path.join(report_dir, file)
                            try:
                                os.remove(filepath)
                                deleted_count += 1
                            except:
                                pass
                    Display.print_colored(f"Удалено отчетов: {deleted_count}", "success")
                except Exception as e:
                    Display.print_colored(f"Ошибка: {str(e)}", "error")
            else:
                Display.print_colored("Папка отчетов не найдена", "error")

        input("\nНажмите Enter для продолжения...")

    def _open_reports_folder(self):
        report_dir = self.settings.get('reports', 'save_location', Config.REPORT_DIR)

        if not os.path.exists(report_dir):
            try:
                os.makedirs(report_dir, exist_ok=True)
            except Exception as e:
                Display.print_colored(f"Не удалось создать папку: {str(e)}", "error")
                input("\nНажмите Enter для продолжения...")
                return

        try:
            if platform.system() == 'Windows':
                os.startfile(report_dir)
            elif platform.system() == 'Darwin':
                subprocess.Popen(['open', report_dir])
            else:
                subprocess.Popen(['xdg-open', report_dir])
            Display.print_colored("Папка отчетов открыта", "success")
        except Exception as e:
            Display.print_colored(f"Не удалось открыть папку: {str(e)}", "error")

        input("\nНажмите Enter для продолжения...")

    def exit_program(self):
        confirm = input("\nВы уверены, что хотите выйти? (y/n): ").lower()
        if confirm == 'y':
            Display.clear_screen()
            print("\n" + "=" * 60)
            Display.print_colored(" HACK LOAD завершает работу ", "info")
            print("=" * 60)

            try:
                self.settings.save_settings()
            except:
                pass

            time.sleep(1)
            self.running = False
            sys.exit(0)


def check_dependencies():
    required = {
        'pyfiglet': 'pyfiglet',
        'requests': 'requests',
        'beautifulsoup4': 'bs4',
        'Pillow': 'PIL',
        'phonenumbers': 'phonenumbers'
    }

    optional = {
        'dnspython': 'dns.resolver'
    }

    missing_required = []
    missing_optional = []

    for module, import_name in required.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_required.append(module)

    for module, import_name in optional.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_optional.append(module)

    if missing_required:
        print("\nНе установлены необходимые библиотеки:")
        for lib in missing_required:
            print(f"  - {lib}")
        print("\nУстановите командой:")
        print("pip install " + " ".join(missing_required))
        return False

    if missing_optional:
        print("\nНе установлены опциональные библиотеки:")
        for lib in missing_optional:
            print(f"  - {lib}")
        print("\nНекоторые функции могут быть недоступны")
        print("Установите командой:")
        print("pip install " + " ".join(missing_optional))
        input("\nНажмите Enter чтобы продолжить...")

    return True


def setup_directories():
    directories = [Config.REPORT_DIR, Config.CACHE_DIR]

    for directory in directories:
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception as e:
                print(f"Не удалось создать папку {directory}: {str(e)}")
                return False

    return True


def main():
    print("\nИнициализация HACK LOAD...")

    if not check_dependencies():
        input("\nНажмите Enter для выхода...")
        sys.exit(1)

    if not setup_directories():
        print("Предупреждение: не удалось создать все необходимые папки")
        print("Программа будет использовать временные папки")
        input("\nНажмите Enter чтобы продолжить...")

    try:
        app = HackLoad()
        app.run()
    except KeyboardInterrupt:
        print("\n\nПрограмма завершена пользователем")
    except Exception as e:
        print(f"\nКритическая ошибка: {str(e)}")
        import traceback
        traceback.print_exc()
        input("\nНажмите Enter для выхода...")
        sys.exit(1)


if __name__ == "__main__":
    main()