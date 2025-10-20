"""
Lambda function for Gameplay Analysis Action Group.
Handles video analysis using Bedrock Data Automation and highlight generation.
"""

import json
import os
import uuid
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import boto3

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import shared helpers
try:
    # Try Lambda Layer path first
    import sys
    sys.path.append('/opt/python')
    from shared.aws_helpers import (
        invoke_data_automation_and_get_results,
        get_bedrock_data_automation_client,
        list_bedrock_projects,
        get_bedrock_project
    )
except ImportError:
    # Fall back to local import from shared directory
    from shared.aws_helpers import (
        invoke_data_automation_and_get_results,
        get_bedrock_data_automation_client,
        list_bedrock_projects,
        get_bedrock_project
    )


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for gameplay analysis operations.
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Extract the action group, API path, and HTTP method
        action_group = event.get('actionGroup', '')
        api_path = event.get('apiPath', '')
        http_method = event.get('httpMethod', '')
        
        # Extract session attributes (contains S3 URI passed from backend)
        session_attributes = {}
        if 'sessionAttributes' in event:
            session_attributes = event['sessionAttributes']
            logger.info(f"Session attributes: {session_attributes}")
        
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
        
        # Merge session attributes into request body for convenience
        # This allows Lambda to access videoS3Uri and videoId from session
        if session_attributes:
            request_body.update({
                's3Uri': session_attributes.get('videoS3Uri', request_body.get('s3Uri')),
                'videoId': session_attributes.get('videoId', request_body.get('videoId'))
            })
        
        # Route to appropriate handler based on API path
        if api_path == '/analyze-video' and http_method == 'POST':
            return handle_analyze_video(request_body, event)
        elif api_path == '/generate-highlights' and http_method == 'POST':
            return handle_generate_highlights(request_body, event)
        elif api_path == '/get-analysis-results' and http_method == 'GET':
            return handle_get_analysis_results(parameters, event)
        else:
            return create_error_response(f"Unknown API path: {api_path}", event)
            
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_error_response(str(e), event)


def handle_analyze_video(request_body: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Start video analysis using Bedrock Data Automation.
    S3 URI can come from request body or session attributes.
    """
    try:
        video_id = request_body.get('videoId')
        s3_uri = request_body.get('s3Uri')
        project_arn = request_body.get('projectArn') or os.environ.get('DATA_AUTOMATION_PROJECT_ARN')
        analysis_type = request_body.get('analysisType', 'both')
        
        logger.info(f"Analyzing video - videoId: {video_id}, s3Uri: {s3_uri}")
        
        if not s3_uri:
            return create_error_response("s3Uri is required (should be provided via session attributes)", event)
        
        if not video_id:
            # Generate a video ID if not provided
            video_id = str(uuid.uuid4())
            logger.info(f"Generated video ID: {video_id}")
        
        if not project_arn:
            return create_error_response("projectArn is required or DATA_AUTOMATION_PROJECT_ARN must be set", event)
        
        # Update video status to processing
        # update_video_status(video_id, 'processing', 0, 'Starting Bedrock Data Automation analysis...')
        
        # Start real Bedrock Data Automation job
        analysis_id = str(uuid.uuid4())
        
        # Use the actual Bedrock Data Automation service
        # Note: invoke_data_automation_and_get_results is async and returns results after polling
        job_response = asyncio.run(
            invoke_data_automation_and_get_results(
                s3_uri=s3_uri,
                project_arn=project_arn
            )
        )
        
        # Store analysis metadata with real job information
        analysis_record = {
            'analysisId': analysis_id,
            'videoId': video_id,
            's3Uri': s3_uri,
            'projectArn': project_arn,
            'analysisType': analysis_type,
            'status': 'processing',
            'startTime': datetime.utcnow().isoformat(),
            'bedrockJobId': job_response.get('jobId'),
            'bedrockJobArn': job_response.get('jobArn'),
            'outputS3Prefix': f"analysis-results/{video_id}/"
        }
        
        # Store analysis metadata
        store_analysis_metadata(analysis_record)
        
        # Update video status with job information
        update_video_status(
            video_id, 
            'processing', 
            10, 
            f'Bedrock Data Automation job started: {job_response.get("jobId")}'
        )
        
        response_body = {
            'videoId': video_id,
            'analysisId': analysis_id,
            'status': 'processing',
            'bedrockJobId': job_response.get('jobId'),
            'estimatedCompletionTime': '5-15 minutes'
        }
        
        return create_success_response(response_body, event)
        
    except Exception as e:
        logger.error(f"Error in handle_analyze_video: {str(e)}")
        return create_error_response(str(e), event)


def handle_generate_highlights(request_body: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate highlights from analyzed video data.
    """
    try:
        video_id = request_body.get('videoId')
        highlight_type = request_body.get('highlightType', 'all')
        max_highlights = request_body.get('maxHighlights', 10)
        min_duration = request_body.get('minDuration', 5)
        
        if not video_id:
            return create_error_response("videoId is required", event)
        
        # Get analysis results for the video
        analysis_results = get_analysis_from_db(video_id)
        
        if not analysis_results:
            return create_error_response(f"No analysis results found for video {video_id}", event)
        
        # Generate highlights based on analysis data
        highlights = generate_highlights_from_analysis(
            analysis_results, 
            highlight_type, 
            max_highlights, 
            min_duration
        )
        
        # Generate summary
        summary = generate_video_summary(analysis_results)
        
        response_body = {
            'videoId': video_id,
            'highlights': highlights,
            'summary': summary
        }
        
        return create_success_response(response_body, event)
        
    except Exception as e:
        logger.error(f"Error in handle_generate_highlights: {str(e)}")
        return create_error_response(str(e), event)


def handle_get_analysis_results(parameters: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieve analysis results for a video.
    """
    try:
        video_id = parameters.get('videoId')
        include_raw_data = parameters.get('includeRawData', 'false').lower() == 'true'
        
        if not video_id:
            return create_error_response("videoId is required", event)
        
        # Get analysis results from database
        analysis_results = get_analysis_from_db(video_id)
        
        if not analysis_results:
            return create_error_response(f"No analysis results found for video {video_id}", event)
        
        # Prepare response
        response_body = {
            'videoId': video_id,
            'analysisStatus': analysis_results.get('status', 'unknown'),
            'processingTime': analysis_results.get('processingTime', '')
        }
        
        # Add analysis outputs
        if 'standardOutput' in analysis_results:
            response_body['standardOutput'] = analysis_results['standardOutput']
        
        if 'customOutput' in analysis_results:
            response_body['customOutput'] = analysis_results['customOutput']
        
        # Add metadata
        if 'metadata' in analysis_results:
            response_body['metadata'] = analysis_results['metadata']
        
        # Remove raw data if not requested
        if not include_raw_data:
            # Remove large raw data fields to reduce response size
            if 'standardOutput' in response_body:
                response_body['standardOutput'] = filter_raw_data(response_body['standardOutput'])
            if 'customOutput' in response_body:
                response_body['customOutput'] = filter_raw_data(response_body['customOutput'])
        
        return create_success_response(response_body, event)
        
    except Exception as e:
        logger.error(f"Error in handle_get_analysis_results: {str(e)}")
        return create_error_response(str(e), event)


def trigger_async_analysis(analysis_record: Dict[str, Any]) -> None:
    """
    Trigger asynchronous video analysis.
    In a real implementation, this would use SQS, Step Functions, or another async mechanism.
    """
    try:
        # For demonstration, we'll simulate the analysis process
        # In production, this would trigger a separate Lambda or Step Function
        
        sqs = boto3.client('sqs')
        queue_url = os.environ.get('ANALYSIS_QUEUE_URL')
        
        if queue_url:
            message = {
                'analysisRecord': analysis_record,
                'action': 'start_analysis'
            }
            
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message)
            )
            
            logger.info(f"Triggered async analysis for {analysis_record['videoId']}")
        
    except Exception as e:
        logger.error(f"Error triggering async analysis: {str(e)}")


def generate_highlights_from_analysis(
    analysis_results: Dict[str, Any], 
    highlight_type: str, 
    max_highlights: int, 
    min_duration: int
) -> List[Dict[str, Any]]:
    """
    Generate highlights from analysis results.
    """
    highlights = []
    
    try:
        # Extract highlights from custom output (sports-specific analysis)
        custom_output = analysis_results.get('customOutput', {})
        
        if 'player_actions' in custom_output:
            for action in custom_output['player_actions'][:max_highlights]:
                if highlight_type == 'all' or action.get('type', '').lower() in highlight_type.lower():
                    highlight = {
                        'title': f"{action.get('player', 'Player')} - {action.get('action', 'Action')}",
                        'description': action.get('description', ''),
                        'startTime': action.get('timestamp', '00:00:00'),
                        'endTime': action.get('end_timestamp', '00:00:05'),
                        'type': action.get('type', 'action'),
                        'confidence': action.get('confidence', 0.8),
                        'players': [action.get('player', '')]
                    }
                    highlights.append(highlight)
        
        # Extract highlights from standard output
        standard_output = analysis_results.get('standardOutput', {})
        
        if 'chapters' in standard_output:
            for chapter in standard_output['chapters'][:max_highlights]:
                if len(highlights) >= max_highlights:
                    break
                    
                highlight = {
                    'title': chapter.get('title', 'Chapter'),
                    'description': chapter.get('summary', ''),
                    'startTime': chapter.get('start_timestamp', '00:00:00'),
                    'endTime': chapter.get('end_timestamp', '00:00:30'),
                    'type': 'chapter',
                    'confidence': 0.9,
                    'players': []
                }
                highlights.append(highlight)
        
    except Exception as e:
        logger.error(f"Error generating highlights: {str(e)}")
    
    return highlights[:max_highlights]


def generate_video_summary(analysis_results: Dict[str, Any]) -> str:
    """
    Generate a comprehensive video summary from analysis results.
    """
    try:
        summary_parts = []
        
        # Add custom analysis summary
        custom_output = analysis_results.get('customOutput', {})
        if 'game_context' in custom_output:
            context = custom_output['game_context']
            teams = context.get('teams', [])
            venue = context.get('venue', '')
            
            if teams and venue:
                summary_parts.append(f"Game between {' vs '.join(teams)} at {venue}")
        
        # Add key player actions
        if 'player_actions' in custom_output:
            actions = custom_output['player_actions'][:3]  # c
            for action in actions:
                summary_parts.append(f"{action.get('player', 'Player')} {action.get('action', 'action')}")
        
        # Add standard analysis summary
        standard_output = analysis_results.get('standardOutput', {})
        if 'summary' in standard_output:
            summary_parts.append(standard_output['summary'])
        
        return '. '.join(summary_parts) if summary_parts else "Video analysis completed successfully."
        
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        return "Video analysis completed successfully."


def update_video_status(video_id: str, status: str, progress: int, message: str) -> None:
    """
    Update video processing status in S3 metadata.
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('AWS_BUCKET_NAME')
        
        metadata_key = f"metadata/videos/{video_id}.json"
        
        # Get existing metadata
        try:
            response = s3_client.get_object(Bucket=bucket_name, Key=metadata_key)
            video_data = json.loads(response['Body'].read().decode('utf-8'))
        except s3_client.exceptions.NoSuchKey:
            # Create new metadata if doesn't exist
            video_data = {'videoId': video_id}
        
        # Update status fields
        video_data.update({
            'status': status,
            'progress': progress,
            'message': message,
            'lastUpdated': datetime.utcnow().isoformat()
        })
        
        # Save back to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=metadata_key,
            Body=json.dumps(video_data, indent=2),
            ContentType='application/json'
        )
        
        logger.info(f"Updated status for video {video_id}: {status}")
        
    except Exception as e:
        logger.error(f"Error updating video status: {str(e)}")


def store_analysis_metadata(analysis_record: Dict[str, Any]) -> None:
    """
    Store analysis metadata in S3.
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('AWS_BUCKET_NAME')
        
        video_id = analysis_record.get('videoId')
        metadata_key = f"metadata/analysis/{video_id}.json"
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=metadata_key,
            Body=json.dumps(analysis_record, indent=2),
            ContentType='application/json'
        )
        
        logger.info(f"Stored analysis metadata for {analysis_record['analysisId']}")
        
    except Exception as e:
        logger.error(f"Error storing analysis metadata: {str(e)}")


def get_analysis_from_db(video_id: str) -> Dict[str, Any]:
    """
    Retrieve analysis results from S3.
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('AWS_BUCKET_NAME')
        
        # Try to get analysis metadata
        metadata_key = f"metadata/analysis/{video_id}.json"
        
        try:
            response = s3_client.get_object(Bucket=bucket_name, Key=metadata_key)
            analysis_data = json.loads(response['Body'].read().decode('utf-8'))
            return analysis_data
        except s3_client.exceptions.NoSuchKey:
            logger.warning(f"Analysis metadata not found for {video_id}")
            return {}
        
    except Exception as e:
        logger.error(f"Error retrieving analysis from S3: {str(e)}")
        return {}


def filter_raw_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter out large raw data fields to reduce response size.
    """
    filtered_data = data.copy()
    
    # Remove large fields that aren't needed for summary responses
    fields_to_remove = ['raw_transcript', 'frame_data', 'audio_data']
    
    for field in fields_to_remove:
        if field in filtered_data:
            del filtered_data[field]
    
    return filtered_data


def create_success_response(body: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a successful response for Bedrock Agent.
    """
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': 'GameplayAnalysis',
            'apiPath': event.get('apiPath', ''),
            'httpMethod': event.get('httpMethod', ''),
            'httpStatusCode': 200,
            'responseBody': {
                'application/json': {
                    'body': json.dumps(body)
                }
            }
        }
    }


def create_error_response(error_message: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create an error response for Bedrock Agent.
    """
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': 'GameplayAnalysis',
            'apiPath': event.get('apiPath', ''),
            'httpMethod': event.get('httpMethod', ''),
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
