import requests
import pytz
from typing import Optional, Dict, Tuple
from datetime import datetime
import os
from fastapi import Request

class GeoTimezoneService:
    def __init__(self):
        self.default_timezone = os.getenv("DEFAULT_TIMEZONE", "UTC")
        self.ipgeolocation_api_key = os.getenv("IPGEOLOCATION_API_KEY")
    
    def get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers first (for reverse proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        client_host = request.client.host if request.client else "127.0.0.1"
        
        # Handle localhost/private IPs - Use Indian IP for testing
        if client_host in ["127.0.0.1", "::1", "localhost"] or client_host.startswith("192.168.") or client_host.startswith("10.") or client_host.startswith("172."):
            return "203.192.1.1"  # Indian IP range instead of 8.8.8.8
        
        return client_host
    
    async def get_timezone_from_ip(self, ip_address: str) -> Tuple[str, Optional[Dict]]:
        """Get timezone and location info from IP address"""
        try:
            # Using ip-api.com (free, no API key required)
            response = await self._get_timezone_from_ipapi(ip_address)
            if response:
                return response
            
            # incase of failure then default timezone
            return self.default_timezone, None
            
        except Exception as e:
            print(f"Error getting timezone for IP {ip_address}: {e}")
            return self.default_timezone, None
    
    async def _get_timezone_from_ipapi(self, ip_address: str) -> Optional[Tuple[str, Dict]]:
        """Get timezone from ip-api.com (free service)"""
        try:
            url = f"http://ip-api.com/json/{ip_address}?fields=status,timezone,country,regionName,city,lat,lon,isp"
            
            response = requests.get(url, timeout=5)
            data = response.json()
            
            if data.get("status") == "success" and data.get("timezone"):
                timezone_str = data["timezone"]
                location_info = {
                    "country": data.get("country"),
                    "region": data.get("regionName"), 
                    "city": data.get("city"),
                    "latitude": data.get("lat"),
                    "longitude": data.get("lon"),
                    "isp": data.get("isp")
                }
                
                # Validate timezone
                try:
                    pytz.timezone(timezone_str)
                    return timezone_str, location_info
                except pytz.exceptions.UnknownTimeZoneError:
                    return None
                    
        except Exception as e:
            print(f"Error with ip-api.com: {e}")
            return None
    
    async def _get_timezone_from_ipgeolocation(self, ip_address: str) -> Optional[Tuple[str, Dict]]:
        """Get timezone from ipgeolocation.io (requires API key)"""
        try:
            url = f"https://api.ipgeolocation.io/ipgeo"
            params = {
                "apiKey": self.ipgeolocation_api_key,
                "ip": ip_address,
                "fields": "time_zone,country_name,state_prov,city,latitude,longitude,isp"
            }
            
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if data.get("time_zone") and data["time_zone"].get("name"):
                timezone_str = data["time_zone"]["name"]
                location_info = {
                    "country": data.get("country_name"),
                    "region": data.get("state_prov"),
                    "city": data.get("city"),
                    "latitude": float(data.get("latitude", 0)),
                    "longitude": float(data.get("longitude", 0)),
                    "isp": data.get("isp")
                }
                
                # Validate timezone
                try:
                    pytz.timezone(timezone_str)
                    return timezone_str, location_info
                except pytz.exceptions.UnknownTimeZoneError:
                    return None
                    
        except Exception as e:
            print(f"Error with ipgeolocation.io: {e}")
            return None
    
    def convert_to_timezone(self, dt: datetime, timezone_str: str) -> datetime:
        """Convert datetime to specified timezone"""
        try:
            tz = pytz.timezone(timezone_str)
            if dt.tzinfo is None:
                # will Assume UTC if no timezone info
                dt = pytz.UTC.localize(dt)
            return dt.astimezone(tz)
        except Exception:
            return dt
    
    def get_current_time_in_timezone(self, timezone_str: str) -> datetime:
        """Get current time in specified timezone"""
        try:
            tz = pytz.timezone(timezone_str)
            return datetime.now(tz)
        except Exception:
            return datetime.now(pytz.UTC)

geo_timezone_service = GeoTimezoneService()
 