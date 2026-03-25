"""
List Catalog - Predefined bypass lists from trusted sources

Curated lists for common services and regions.
Optimized for embedded devices (128MB RAM).
"""
from typing import Dict, List, Any
import requests
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Catalog of available lists
LIST_CATALOG: Dict[str, Dict[str, Any]] = {
    'anticensor': {
        'name': 'Антицензор',
        'description': 'Обход блокировок Роскомнадзора',
        'url': 'https://raw.githubusercontent.com/zhovner/zaborona_help/master/hosts.txt',
        'format': 'hosts',
    },
    'reestr': {
        'name': 'Реестр запрещённых сайтов',
        'description': 'Официальный реестр запрещённых сайтов РФ',
        'url': 'https://raw.githubusercontent.com/zhovner/zaborona_help/master/reestr.txt',
        'format': 'domains',
    },
    'social': {
        'name': 'Соцсети',
        'description': 'Facebook, Instagram, Twitter, TikTok',
        'domains': [
            'facebook.com',
            'instagram.com',
            'twitter.com',
            'tiktok.com',
            'whatsapp.com',
            'telegram.org',
        ],
        'format': 'domains',
    },
    'streaming': {
        'name': 'Стриминговые сервисы',
        'description': 'Netflix, Spotify, Disney+',
        'domains': [
            'netflix.com',
            'spotify.com',
            'disneyplus.com',
            'hulu.com',
            'amazonprime.com',
        ],
        'format': 'domains',
    },
    'torrents': {
        'name': 'Торрент-трекеры',
        'description': 'RuTracker, ThePirateBay, 1337x',
        'domains': [
            'rutracker.org',
            'thepiratebay.org',
            '1337x.to',
            'torrentz2.eu',
        ],
        'format': 'domains',
    },
}


def get_catalog() -> Dict[str, Dict[str, Any]]:
    """Get full catalog"""
    return LIST_CATALOG


def get_list_info(name: str) -> Dict[str, Any]:
    """Get info about specific list"""
    return LIST_CATALOG.get(name, {})


def download_list(name: str, dest_dir: str) -> tuple:
    """
    Download list from catalog and save to file.
    
    Args:
        name: List name from catalog
        dest_dir: Destination directory
        
    Returns:
        Tuple of (success: bool, message: str, count: int)
    """
    if name not in LIST_CATALOG:
        return False, f"List '{name}' not found", 0
    
    list_info = LIST_CATALOG[name]
    filename = f"{name}.txt"
    filepath = os.path.join(dest_dir, filename)
    
    try:
        # If URL provided, download
        if 'url' in list_info:
            logger.info(f"Downloading {name} from {list_info['url']}")
            response = requests.get(list_info['url'], timeout=30)
            response.raise_for_status()
            
            # Parse and save
            domains = _parse_list(response.text, list_info['format'])
            
        elif 'domains' in list_info:
            # Use predefined domains
            domains = list_info['domains']
            
        else:
            return False, "No data source", 0
        
        # Save to file (atomic write)
        temp_path = filepath + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            for domain in domains:
                f.write(f"{domain}\n")
        
        # Atomic rename
        os.replace(temp_path, filepath)
        
        logger.info(f"Saved {len(domains)} domains to {filepath}")
        return True, f"Downloaded {len(domains)} domains", len(domains)
        
    except requests.RequestException as e:
        logger.error(f"Download error: {e}")
        return False, f"Download error: {e}", 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False, str(e), 0


def _parse_list(content: str, format: str) -> List[str]:
    """
    Parse list content based on format.
    
    Args:
        content: Raw file content
        format: 'hosts' or 'domains'
        
    Returns:
        List of domains
    """
    domains = []
    
    for line in content.split('\n'):
        line = line.strip()
        
        # Skip comments and empty lines
        if not line or line.startswith('#'):
            continue
        
        if format == 'hosts':
            # hosts format: IP DOMAIN
            parts = line.split()
            if len(parts) >= 2 and not parts[0].startswith('#'):
                domain = parts[1]
                if domain != 'localhost':
                    domains.append(domain)
        else:
            # domains format: one per line
            domains.append(line)
    
    return domains
