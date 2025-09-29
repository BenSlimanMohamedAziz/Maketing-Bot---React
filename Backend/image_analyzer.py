# image_analyzer.py
import requests
import json
import numpy as np
from io import BytesIO
from PIL import Image, ImageStat, ImageFilter, ImageEnhance, ImageDraw, ImageFont, ImageOps
import colorsys
from collections import Counter
import re

class LogoAnalyzer:
    """Analyze company logos to extract design characteristics"""
    
    def __init__(self, image_url):
        self.image_url = image_url
        self.image = None
        self.analysis_results = {}
    
    def load_image(self):
        """Download and load the image"""
        try:
            response = requests.get(self.image_url)
            if response.status_code != 200:
                raise Exception(f"Failed to download image: {response.status_code}")
                
            self.image = Image.open(BytesIO(response.content))
            if self.image.mode != 'RGB':
                self.image = self.image.convert('RGB')
            return True
        except Exception as e:
            self.analysis_results["error"] = f"Image loading error: {str(e)}"
            return False
    
    def rgb_to_hsv(self, r, g, b):
        """Convert RGB to HSV"""
        return colorsys.rgb_to_hsv(r/255, g/255, b/255)
    
    def get_color_name(self, r, g, b):
        """Get color name based on RGB values"""
        h, s, v = self.rgb_to_hsv(r, g, b)
        h_deg = h * 360
        
        if s < 0.15:
            if v < 0.15: return "Black"
            elif v < 0.30: return "Dark Gray"
            elif v < 0.60: return "Gray"
            elif v < 0.85: return "Light Gray"
            else: return "White"
        
        color_ranges = [
            (0, 15, "Red"), (15, 45, "Orange"), (45, 70, "Yellow"),
            (70, 160, "Green"), (160, 200, "Cyan"), (200, 260, "Blue"),
            (260, 320, "Purple"), (320, 360, "Pink")
        ]
        
        for low, high, name in color_ranges:
            if low <= h_deg <= high:
                prefix = "Vibrant " if s > 0.7 else ("Pale " if s < 0.4 else "")
                brightness = "Dark " if v < 0.3 else ("Light " if v > 0.7 else "")
                return f"{brightness}{prefix}{name}"
        return "Unknown"

    def extract_dominant_colors(self):
        """Extract dominant colors from logo"""
        try:
            img_small = self.image.resize((100, 100))
            result = img_small.convert('P', palette=Image.ADAPTIVE, colors=5)
            palette = result.getpalette()
            color_counts = Counter(result.getdata())
            
            colors = []
            for i, count in color_counts.most_common(5):
                r, g, b = palette[i*3], palette[i*3+1], palette[i*3+2]
                percent = count / (img_small.width * img_small.height) * 100
                if max(r, g, b) < 10 and percent < 5:
                    continue
                    
                colors.append({
                    "name": self.get_color_name(r, g, b),
                    "hex": f"#{r:02x}{g:02x}{b:02x}",
                    "rgb": (r, g, b),
                    "percentage": round(percent, 1)
                })
            
            self.analysis_results["colors"] = colors
            return True
        except Exception as e:
            self.analysis_results["error"] = f"Color analysis error: {str(e)}"
            return False
    
    def analyze_logo(self):
        """Run full logo analysis"""
        if not self.load_image():
            return None
        
        if not self.extract_dominant_colors():
            return None
            
        return self.analysis_results

def get_logo_description(logo_url):
    """Get a natural language description of a logo"""
    analyzer = LogoAnalyzer(logo_url)
    analysis = analyzer.analyze_logo()
    
    if not analysis or "error" in analysis:
        return "Unable to analyze logo design"
    
    description = "Logo design analysis: "
    if "colors" in analysis and analysis["colors"]:
        colors = analysis["colors"]
        main_color = colors[0]
        description += f"Primary color is {main_color['name']} ({main_color['hex']}), "
        
        if len(colors) > 1:
            secondary_colors = [f"{c['name']} ({c['hex']})" for c in colors[1:3]]
            description += f"with secondary colors {', '.join(secondary_colors)}. "
    
    return description