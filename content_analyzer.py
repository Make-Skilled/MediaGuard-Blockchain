import torch
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import numpy as np
from typing import Tuple, Optional

# Initialize CLIP model
try:
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    model.eval()
except Exception as e:
    print(f"Error loading CLIP model: {e}")
    model = None
    processor = None

def calculate_vulgarity_score(image_features, text_features, inappropriate_features, safe_features):
    """Calculate a numerical vulgarity score between 0.0 and 1.0."""
    # Calculate similarity scores
    inappropriate_scores = torch.cosine_similarity(image_features, inappropriate_features)
    safe_scores = torch.cosine_similarity(image_features, safe_features)
    
    # Get maximum scores
    max_inappropriate = torch.max(inappropriate_scores).item()
    max_safe = torch.max(safe_scores).item()
    
    # Calculate score (0.0 to 1.0)
    total = max_inappropriate + max_safe
    if total == 0:
        return 0.0
    score = max_inappropriate / total
    
    return score

def analyze_content(image: Image.Image) -> Tuple[float, str, bool]:
    """
    Analyze an image for inappropriate content using CLIP model.
    
    Args:
        image: PIL Image object to analyze
        
    Returns:
        Tuple containing:
        - float: Vulgarity score (0.0 to 1.0)
        - str: Category of content
        - bool: Whether the content is safe
    """
    try:
        if model is None or processor is None:
            print("CLIP model not loaded, returning safe defaults")
            return 0.0, 'safe', True
            
        # Convert image to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Define text prompts for different categories
        inappropriate_prompts = [
            "inappropriate content", "explicit content", "adult content",
            "violence", "graphic content", "disturbing content"
        ]
        safe_prompts = [
            "safe content", "family friendly", "appropriate content",
            "wholesome content", "child friendly", "clean content"
        ]
        
        # Process image
        inputs = processor(images=image, return_tensors="pt", padding=True)
        image_features = model.get_image_features(**inputs)
        
        # Process text prompts
        inappropriate_text = processor(text=inappropriate_prompts, return_tensors="pt", padding=True)
        safe_text = processor(text=safe_prompts, return_tensors="pt", padding=True)
        
        inappropriate_features = model.get_text_features(**inappropriate_text)
        safe_features = model.get_text_features(**safe_text)
        
        # Calculate vulgarity score
        vulgarity_score = calculate_vulgarity_score(
            image_features, None, inappropriate_features, safe_features
        )
        
        # Determine category based on score
        if vulgarity_score < 0.3:
            content_category = 'safe'
        elif vulgarity_score < 0.5:
            content_category = 'mild'
        elif vulgarity_score < 0.7:
            content_category = 'moderate'
        else:
            content_category = 'explicit'
        
        # Determine if content is safe
        is_safe = vulgarity_score < 0.5
        
        return vulgarity_score, content_category, is_safe
        
    except Exception as e:
        print(f"Error analyzing content: {str(e)}")
        return 0.0, 'safe', True  # Return safe defaults in case of error 