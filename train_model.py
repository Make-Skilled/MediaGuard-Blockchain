import os
import tensorflow as tf
import numpy as np
from PIL import Image
import cv2
from moviepy.editor import VideoFileClip
import logging
from transformers import CLIPProcessor, CLIPModel
import torch
from huggingface_hub import login

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create uploads directory if it doesn't exist
UPLOAD_DIR = 'uploads'
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Authenticate with Hugging Face
HF_TOKEN = ""
login(token=HF_TOKEN)

class ContentAnalyzer:
    def __init__(self):
        self.model = None
        self.processor = None
        self.image_size = (224, 224)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Content categories with multiple prompts
        self.category_prompts = {
            'romance': [
                "a romantic couple in love",
                "people showing affection or romance",
                "romantic dating scene",
                "romantic relationship moment",
                "intimate couple moment"
            ],
            'explicit': [
                "adult content warning",
                "explicit content warning",
                "NSFW content warning",
                "inappropriate adult content",
                "age-restricted content"
            ],
            'implicit': [
                "suggestive content",
                "provocative scene",
                "subtle adult themes",
                "implied mature content",
                "suggestive but not explicit content"
            ],
            'safe': [
                "safe for work content",
                "family-friendly image",
                "appropriate general content",
                "clean and safe content",
                "normal everyday scene"
            ]
        }
        
        # Confidence thresholds
        self.thresholds = {
            'romance': 0.4,
            'explicit': 0.3,
            'implicit': 0.35,
            'safe': 0.45
        }
        
        self.categories = list(self.category_prompts.keys())
        
    def create_model(self):
        try:
            # Use CLIP model from OpenAI
            model_name = "openai/clip-vit-large-patch14"  # Using larger model for better accuracy
            logger.info(f"Loading CLIP model: {model_name}")
            
            # Load model and processor
            self.model = CLIPModel.from_pretrained(model_name)
            self.processor = CLIPProcessor.from_pretrained(model_name)
            
            # Move model to appropriate device
            self.model = self.model.to(self.device)
            self.model.eval()
            
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            raise Exception(f"Failed to load model: {str(e)}")
        
    def analyze_image(self, image_path):
        try:
            if self.model is None:
                self.create_model()
            
            # Check if image path exists
            if isinstance(image_path, str):
                if not os.path.exists(image_path):
                    raise FileNotFoundError(f"Image file not found: {image_path}")
                image = Image.open(image_path)
            else:
                image = image_path  # Assume it's already a PIL Image
            
            # Ensure image is in RGB mode
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Initialize results
            results = {
                'romance': 0.0,
                'explicit': 0.0,
                'implicit': 0.0,
                'safe': 0.0,
                'total_frames': 1
            }
            
            # Process each category with multiple prompts
            for category, prompts in self.category_prompts.items():
                # Process inputs for all prompts in this category
                inputs = self.processor(
                    images=[image] * len(prompts),
                    text=prompts,
                    return_tensors="pt",
                    padding=True
                ).to(self.device)
                
                # Get model predictions
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    logits_per_image = outputs.logits_per_image
                    probs = torch.nn.functional.softmax(logits_per_image, dim=1)
                
                # Take the maximum probability across all prompts for this category
                category_score = float(torch.max(probs).cpu().numpy())
                
                # Apply threshold
                if category_score >= self.thresholds[category]:
                    results[category] = category_score
                
                logger.info(f"Category {category} score: {category_score}")
            
            # Normalize results
            total_score = sum(results[cat] for cat in self.categories)
            if total_score > 0:
                for category in self.categories:
                    results[category] = float(results[category] / total_score)
            
            # If no category meets threshold, default to safe
            if all(results[cat] == 0.0 for cat in self.categories):
                results['safe'] = 1.0
            
            logger.info(f"Final results: {results}")
            return results
            
        except FileNotFoundError as e:
            logger.error(f"File not found error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error analyzing image: {str(e)}")
            raise Exception(f"Failed to analyze image: {str(e)}")
    
    def analyze_video(self, video_path):
        try:
            if self.model is None:
                self.create_model()
            
            # Check if video path exists
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # Load video
            video = VideoFileClip(video_path)
            duration = video.duration
            fps = video.fps
            total_frames = int(duration * fps)
            
            # Initialize results
            results = {
                'romance': 0,
                'explicit': 0,
                'implicit': 0,
                'safe': 0,
                'total_frames': total_frames
            }
            
            # Sample frames for analysis (every 30th frame)
            frame_count = 0
            for frame in video.iter_frames(fps=fps/30):  # Analyze 1 frame per second
                try:
                    # Convert frame to PIL Image
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame_pil = Image.fromarray(frame_rgb)
                    
                    # Analyze frame
                    frame_results = self.analyze_image(frame_pil)
                    
                    # Accumulate results
                    for category in self.categories:
                        results[category] += frame_results[category]
                    
                    frame_count += 1
                except Exception as e:
                    logger.error(f"Error processing frame: {str(e)}")
                    continue
            
            # Average the results
            if frame_count > 0:
                for category in self.categories:
                    results[category] /= frame_count
            
            return results
            
        except FileNotFoundError as e:
            logger.error(f"File not found error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error analyzing video: {str(e)}")
            raise Exception(f"Failed to analyze video: {str(e)}")

def prepare_dataset_structure():
    """Create the necessary directories for the dataset"""
    # Create main directories
    for directory in ['data', 'uploads']:
        os.makedirs(directory, exist_ok=True)
    
    # Create category subdirectories
    for split in ['train', 'val', 'test']:
        for category in ['romance', 'explicit', 'implicit', 'safe']:
            os.makedirs(f'data/{split}/{category}', exist_ok=True)

if __name__ == '__main__':
    # Create dataset structure
    prepare_dataset_structure()
    
    # Initialize the analyzer
    analyzer = ContentAnalyzer()
    analyzer.create_model() 