"""
Lambda function for Video Management Action Group.
Handles video upload, storage, and inventory management.
"""

import json
import os
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List
import boto3

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import shared helpers with fallback
try:
    # Try Lambda Layer path first
    import sys
    sys.path.append('/opt/python')
    from aws_helpers import (
        generate_presigned_upload_url,
        get_s3_client,
        get_bucket_name
    )
except ImportError:
    # Fall back to local import from shared directory
    from shared.aws_helpers import (
        generate_presigned_upload_url,
        get_s3_client,
        get_bucket_name
    )


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for video management operations.
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Extract the action group, API path, and HTTP method
        action_group = event.get('actionGroup', '')
        api_path = event.get('apiPath', '')
        http_method = event.get('httpMethod', '')
        
        # Extract parameters from the event
        parameters = {}
        if 'parameters' in event:
            for param in event['parameters']:
                parameters[param['name']] = param['value']
        
        # Extract request body if present
        request_body = {}
        if 'requestBody' in event and 'content' in event['requestBody']:
            content = event['requestBody']['content']
            if 'application/json' in content:
                request_body = json.loads(content['application/json']['properties'])
        
        # Route to appropriate handler based on API path
        if api_path == '/upload-video' and http_method == 'POST':
            return handle_upload_video(request_body, api_path, http_method)
        elif api_path == '/list-videos' and http_method == 'GET':
            return handle_list_videos(parameters, api_path, http_method)
        elif api_path == '/video-status' and http_method == 'GET':
            return handle_video_status(parameters, api_path, http_method)
        else:
            return create_error_response(f"Unknown API path: {api_path}", api_path, http_method)
            
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_error_response(str(e), api_path, http_method)


def handle_upload_video(request_body: Dict[str, Any], api_path: str = '', http_method: str = '') -> Dict[str, Any]:
    """
    Generate presigned URL for video upload.
    """
    try:
        file_name = request_body.get('fileName')
        content_type = request_body.get('contentType', 'video/mp4')
        
        if not file_name:
            return create_error_response("fileName is required", api_path, http_method)
        
        # Generate presigned URL
        upload_info = generate_presigned_upload_url(file_name, content_type)
        
        # Create video record in DynamoDB
        video_id = str(uuid.uuid4())
        video_record = {
            'videoId': video_id,
            'fileName': file_name,
            's3Uri': upload_info['s3_uri'],
            'uploadTime': datetime.utcnow().isoformat(),
            'status': 'uploaded',
            'contentType': content_type
        }
        
        # Store video metadata
        store_video_metadata(video_record)
        
        response_body = {
            'uploadUrl': upload_info['upload_url'],
            's3Uri': upload_info['s3_uri'],
            'videoId': video_id
        }
        
        return create_success_response(response_body, api_path, http_method)
        
    except Exception as e:
        logger.error(f"Error in handle_upload_video: {str(e)}")
        return create_error_response(str(e), api_path, http_method)


def handle_list_videos(parameters: Dict[str, Any], api_path: str = '', http_method: str = '') -> Dict[str, Any]:
    """
    List analyzed videos with optional filtering.
    """
    try:
        limit = int(parameters.get('limit', 50))
        status_filter = parameters.get('status')
        
        # Get videos from DynamoDB
        videos = get_videos_from_db(limit, status_filter)
        
        response_body = {
            'videos': videos
        }
        
        return create_success_response(response_body, api_path, http_method)
        
    except Exception as e:
        logger.error(f"Error in handle_list_videos: {str(e)}")
        return create_error_response(str(e), api_path, http_method)


def handle_video_status(parameters: Dict[str, Any], api_path: str = '', http_method: str = '') -> Dict[str, Any]:
    """
    Get video processing status.
    """
    try:
        video_id = parameters.get('videoId')
        
        if not video_id:
            return create_error_response("videoId is required", api_path, http_method)
        
        # Get video status from DynamoDB
        video_info = get_video_from_db(video_id)
        
        if not video_info:
            return create_error_response(f"Video {video_id} not found", api_path, http_method)
        
        response_body = {
            'videoId': video_id,
            'status': video_info.get('status', 'unknown'),
            'progress': video_info.get('progress', 0),
            'message': video_info.get('message', '')
        }
        
        return create_success_response(response_body, api_path, http_method)
        
    except Exception as e:
        logger.error(f"Error in handle_video_status: {str(e)}")
        return create_error_response(str(e), api_path, http_method)


def store_video_metadata(video_record: Dict[str, Any]) -> None:
    """
    Store video metadata in S3.
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('AWS_BUCKET_NAME')
        
        metadata_key = f"metadata/videos/{video_record['videoId']}.json"
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=metadata_key,
            Body=json.dumps(video_record, indent=2),
            ContentType='application/json'
        )
        
        logger.info(f"Stored video metadata for {video_record['videoId']} in S3")
        
    except Exception as e:
        logger.error(f"Error storing video metadata: {str(e)}")
        raise


def get_videos_from_db(limit: int, status_filter: str = None) -> List[Dict[str, Any]]:
    """
    Retrieve videos from S3 metadata with optional filtering.
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('AWS_BUCKET_NAME')
        
        # List all video metadata files
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix='metadata/videos/',
            MaxKeys=limit
        )
        
        videos = []
        if 'Contents' in response:
            for obj in response['Contents']:
                try:
                    # Get each metadata file
                    metadata_response = s3_client.get_object(
                        Bucket=bucket_name,
                        Key=obj['Key']
                    )
                    video_data = json.loads(metadata_response['Body'].read().decode('utf-8'))
                    
                    # Apply status filter if provided
                    if status_filter is None or video_data.get('status') == status_filter:
                        videos.append(video_data)
                        
                except Exception as e:
                    logger.warning(f"Error reading video metadata {obj['Key']}: {str(e)}")
                    continue
        
        return videos[:limit]
        
    except Exception as e:
        logger.error(f"Error retrieving videos from S3: {str(e)}")
        return []


def get_video_from_db(video_id: str) -> Dict[str, Any]:
    """
    Retrieve a specific video metadata from S3.
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('AWS_BUCKET_NAME')
        
        metadata_key = f"metadata/videos/{video_id}.json"
        
        response = s3_client.get_object(Bucket=bucket_name, Key=metadata_key)
        video_data = json.loads(response['Body'].read().decode('utf-8'))
        
        return video_data
        
    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"Video metadata not found for {video_id}")
        return {}
    except Exception as e:
        logger.error(f"Error retrieving video from S3: {str(e)}")
        return {}


def create_success_response(body: Dict[str, Any], api_path: str = '', http_method: str = '') -> Dict[str, Any]:
    """
    Create a successful response for Bedrock Agent.
    """
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': 'VideoManagement',
            'apiPath': api_path,
            'httpMethod': http_method,
            'httpStatusCode': 200,
            'responseBody': {
                'application/json': {
                    'body': json.dumps(body)
                }
            }
        }
    }


def create_error_response(error_message: str, api_path: str = '', http_method: str = '') -> Dict[str, Any]:
    """
    Create an error response for Bedrock Agent.
    """
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': 'VideoManagement',
            'apiPath': api_path,
            'httpMethod': http_method,
            'httpStatusCode': 400,
            'responseBody': {
                'application/json': {
                    'body': json.dumps({
                        'error': error_message
                    })
                }
            }
        }
    }
