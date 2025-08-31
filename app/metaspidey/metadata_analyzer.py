import os
import json
import mimetypes
from datetime import datetime
import hashlib
from pathlib import Path

# Try to import optional libraries, fall back gracefully if not available
try:
    from PIL import Image
    from PIL.ExifTags import TAGS as EXIF_TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

class MetadataAnalyzer:
    """Metadata analyzer adapted for the Flask application"""
    
    def __init__(self):
        if MAGIC_AVAILABLE:
            self.mime = magic.Magic(mime=True)
        else:
            self.mime = None

    def get_file_hash(self, filepath):
        """Calculate file hashes"""
        hashes = {}
        hash_functions = {
            'MD5': hashlib.md5(),
            'SHA1': hashlib.sha1(),
            'SHA256': hashlib.sha256()
        }
        
        try:
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    for hash_func in hash_functions.values():
                        hash_func.update(chunk)
            
            for name, hash_func in hash_functions.items():
                hashes[name] = hash_func.hexdigest()
                
        except Exception as e:
            hashes['error'] = str(e)
            
        return hashes

    def get_basic_metadata(self, filepath):
        """Get basic file metadata"""
        try:
            stat = os.stat(filepath)
            file_path = Path(filepath)
            
            # Determine MIME type
            mime_type = None
            if self.mime:
                try:
                    mime_type = self.mime.from_file(filepath)
                except:
                    pass
            
            if not mime_type:
                mime_type, _ = mimetypes.guess_type(filepath)
                if not mime_type:
                    mime_type = 'application/octet-stream'
            
            metadata = {
                'filename': file_path.name,
                'file_path': str(file_path),
                'file_size': stat.st_size,
                'file_size_human': self._format_file_size(stat.st_size),
                'mime_type': mime_type,
                'extension': file_path.suffix.lower(),
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'accessed': datetime.fromtimestamp(stat.st_atime).isoformat(),
                'permissions': oct(stat.st_mode)[-3:],
            }
            
            return metadata
            
        except Exception as e:
            return {'error': str(e)}

    def get_image_metadata(self, filepath):
        """Extract image metadata including EXIF"""
        if not PIL_AVAILABLE:
            return {'error': 'PIL library not available for image analysis'}
        
        try:
            with Image.open(filepath) as img:
                metadata = {
                    'format': img.format,
                    'mode': img.mode,
                    'size': img.size,
                    'width': img.size[0],
                    'height': img.size[1],
                    'has_transparency': img.mode in ('RGBA', 'LA') or 'transparency' in img.info
                }
                
                # Extract EXIF data
                exif_data = {}
                if hasattr(img, '_getexif') and img._getexif() is not None:
                    exif = img._getexif()
                    for tag_id, value in exif.items():
                        tag = EXIF_TAGS.get(tag_id, tag_id)
                        # Convert bytes to string for JSON serialization
                        if isinstance(value, bytes):
                            try:
                                value = value.decode('utf-8', errors='ignore')
                            except:
                                value = str(value)
                        exif_data[str(tag)] = value
                
                metadata['exif'] = exif_data
                return metadata
                
        except Exception as e:
            return {'error': str(e)}

    def get_document_metadata(self, filepath):
        """Extract document metadata (basic implementation)"""
        metadata = {}
        
        try:
            # Basic document analysis
            with open(filepath, 'rb') as f:
                content = f.read(1024)  # Read first 1KB
                
                # Check for common document signatures
                if content.startswith(b'%PDF'):
                    metadata['document_type'] = 'PDF'
                elif content.startswith(b'PK\x03\x04'):
                    metadata['document_type'] = 'Office Document (ZIP-based)'
                elif b'<?xml' in content:
                    metadata['document_type'] = 'XML-based Document'
                else:
                    metadata['document_type'] = 'Unknown'
                
                # Count text content
                try:
                    text_content = content.decode('utf-8', errors='ignore')
                    metadata['estimated_text_content'] = len(text_content.strip()) > 0
                except:
                    metadata['estimated_text_content'] = False
                    
        except Exception as e:
            metadata['error'] = str(e)
            
        return metadata

    def analyze_file(self, filepath, extract_exif=True, calculate_hashes=True, deep_analysis=False):
        """
        Simplified and robust file analysis
        """
        try:
            if not os.path.exists(filepath):
                return {'error': f'File not found: {filepath}'}
            
            print(f"Analyzing file: {filepath}")
            
            analysis_result = {
                'analysis_timestamp': datetime.now().isoformat(),
                'filename': os.path.basename(filepath),
                'file_path': filepath
            }
            
            # Always get basic metadata
            try:
                basic_meta = self.get_basic_metadata(filepath)
                analysis_result['basic_metadata'] = basic_meta
            except Exception as e:
                analysis_result['basic_metadata'] = {'error': f'Failed to get basic metadata: {str(e)}'}
            
            # Calculate hashes if requested
            if calculate_hashes:
                try:
                    hashes = self.get_file_hash(filepath)
                    analysis_result['hashes'] = hashes
                except Exception as e:
                    analysis_result['hashes'] = {'error': f'Failed to calculate hashes: {str(e)}'}
            
            # Determine file type
            mime_type = analysis_result.get('basic_metadata', {}).get('mime_type', '')
            
            # Image analysis
            if extract_exif and mime_type and mime_type.startswith('image/'):
                try:
                    image_meta = self.get_image_metadata(filepath)
                    analysis_result['image_metadata'] = image_meta
                except Exception as e:
                    analysis_result['image_metadata'] = {'error': f'Failed to analyze image: {str(e)}'}
            
            # Document analysis
            if mime_type and (mime_type.startswith('application/') or mime_type.startswith('text/')):
                try:
                    doc_meta = self.get_document_metadata(filepath)
                    analysis_result['document_metadata'] = doc_meta
                except Exception as e:
                    analysis_result['document_metadata'] = {'error': f'Failed to analyze document: {str(e)}'}
            
            # Deep analysis if requested
            if deep_analysis:
                try:
                    deep_meta = self._perform_deep_analysis(filepath)
                    analysis_result['deep_analysis'] = deep_meta
                except Exception as e:
                    analysis_result['deep_analysis'] = {'error': f'Deep analysis failed: {str(e)}'}
            
            print(f"Analysis completed for: {filepath}")
            return analysis_result
            
        except Exception as e:
            return {
                'error': f'Analysis failed: {str(e)}',
                'filename': os.path.basename(filepath) if filepath else 'unknown',
                'analysis_timestamp': datetime.now().isoformat()
            }
    
    def analyze_directory(self, directory_path, **kwargs):
        """Analyze all files in a directory"""
        try:
            if not os.path.exists(directory_path):
                return {'error': f'Directory not found: {directory_path}'}
            
            if not os.path.isdir(directory_path):
                return {'error': f'Path is not a directory: {directory_path}'}
            
            results = []
            file_count = 0
            
            print(f"Analyzing directory: {directory_path}")
            
            for root, dirs, files in os.walk(directory_path):
                for filename in files:
                    if file_count >= 50:  # Limit for safety
                        break
                    
                    filepath = os.path.join(root, filename)
                    try:
                        result = self.analyze_file(filepath, **kwargs)
                        results.append(result)
                        file_count += 1
                    except Exception as e:
                        results.append({
                            'error': str(e),
                            'filename': filename,
                            'file_path': filepath
                        })
                
                if file_count >= 50:
                    break
            
            return {
                'directory_analysis': True,
                'directory_path': directory_path,
                'total_files_analyzed': len(results),
                'results': results,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'error': f'Directory analysis failed: {str(e)}',
                'directory_path': directory_path,
                'timestamp': datetime.now().isoformat()
            }

    def _perform_deep_analysis(self, filepath):
        """Perform deep file analysis"""
        deep_data = {}
        
        try:
            file_size = os.path.getsize(filepath)
            
            # Entropy analysis (simplified)
            with open(filepath, 'rb') as f:
                chunk = f.read(min(8192, file_size))
                if chunk:
                    # Calculate byte frequency
                    byte_counts = [0] * 256
                    for byte in chunk:
                        byte_counts[byte] += 1
                    
                    # Calculate entropy (simplified)
                    total = len(chunk)
                    entropy = 0
                    for count in byte_counts:
                        if count > 0:
                            p = count / total
                            entropy -= p * (p.bit_length() - 1)
                    
                    deep_data['entropy'] = entropy
                    deep_data['unique_bytes'] = sum(1 for count in byte_counts if count > 0)
            
            # File structure analysis
            deep_data['analysis_depth'] = 'comprehensive'
            
        except Exception as e:
            deep_data['error'] = str(e)
        
        return deep_data

    def _format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

    def batch_analyze(self, file_paths, **kwargs):
        """Analyze multiple files"""
        results = []
        
        for filepath in file_paths:
            result = self.analyze_file(filepath, **kwargs)
            result['source_file'] = filepath
            results.append(result)
        
        return {
            'batch_analysis': True,
            'total_files': len(file_paths),
            'results': results,
            'timestamp': datetime.now().isoformat()
        }