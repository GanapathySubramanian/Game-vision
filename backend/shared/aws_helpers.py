"""
AWS Helper functions for Bedrock Agent Gameplay Analysis.
Migrated and adapted from the original MCP server helpers.
"""

import asyncio
import boto3
import json
import os
import uuid
from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List


# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_region() -> str:
    """Get the AWS region from environment variables."""
    return os.environ.get('AWS_REGION', 'us-east-1')


def get_account_id() -> str:
    """Get the AWS account ID using STS get_caller_identity."""
    session = get_aws_session()
    sts_client = session.client('sts', region_name=get_region())
    try:
        response = sts_client.get_caller_identity()
        return response['Account']
    except Exception as e:
        logger.error(f'Failed to get AWS account ID: {e}')
        raise ValueError(f'Failed to get AWS account ID: {str(e)}')


def get_bucket_name() -> Optional[str]:
    """Get the S3 bucket name from environment variables."""
    bucket_name = os.environ.get('AWS_BUCKET_NAME')
    if not bucket_name:
        raise ValueError('AWS_BUCKET_NAME environment variable is not set')
    return bucket_name


def get_aws_session(region_name=None):
    """Create an AWS session using default AWS credential chain.
    
    This matches the MCP server behavior which uses the default credential chain
    (shared credentials file) instead of named profiles.
    """
    region = region_name or get_region()
    
    # Always use default credential chain (like MCP server does)
    # This will use credentials from ~/.aws/credentials (shared-credentials-file)
    logger.debug('Using default AWS credential chain from ~/.aws/credentials')
    return boto3.Session(region_name=region)


def get_profile_arn() -> Optional[str]:
    """Get the Bedrock Data Automation profile ARN."""
    region = get_region()
    account_id = get_account_id()
    return f'arn:aws:bedrock:{region}:{account_id}:data-automation-profile/us.data-automation-v1'


def get_bedrock_data_automation_client():
    """Get a Bedrock Data Automation client for Data Automation APIs."""
    session = get_aws_session()
    return session.client('bedrock-data-automation', region_name=get_region())


def get_bedrock_data_automation_runtime_client():
    """Get a Bedrock Data Automation Runtime client."""
    session = get_aws_session()
    return session.client('bedrock-data-automation-runtime', region_name=get_region())


def get_bedrock_agent_runtime_client():
    """Get a Bedrock Agent Runtime client."""
    session = get_aws_session()
    return session.client('bedrock-agent-runtime', region_name=get_region())


def get_s3_client():
    """Get an S3 client."""
    session = get_aws_session()
    return session.client('s3', region_name=get_region())


def sanitize_path(file_path: str, base_dir: Optional[str] = None) -> Path:
    """Sanitize and validate a file path to prevent path traversal attacks."""
    if base_dir:
        base_path = Path(base_dir).resolve()
        try:
            full_path = (base_path / file_path).resolve()
            if not str(full_path).startswith(str(base_path)):
                raise ValueError(f'Path {file_path} attempts to traverse outside base directory')
            return full_path
        except Exception as e:
            raise ValueError(f'Invalid path: {str(e)}')

    try:
        return Path(file_path).resolve()
    except Exception as e:
        raise ValueError(f'Invalid path: {str(e)}')


def get_bucket_and_key_from_s3_uri(s3_uri: str) -> Tuple[str, str]:
    """Parse an S3 URI into bucket and key."""
    parts = s3_uri.split('/')
    bucket = parts[2]
    key = '/'.join(parts[3:])
    return bucket, key


async def download_from_s3(s3_uri: str) -> Optional[Dict[str, Any]]:
    """Download and parse a JSON file from S3."""
    bucket, key = get_bucket_and_key_from_s3_uri(s3_uri)

    s3_client = get_s3_client()
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except Exception as e:
        raise ValueError(f'Error downloading from S3: {e}')


async def generate_presigned_upload_url(file_name: str, content_type: str = 'video/mp4') -> Dict[str, str]:
    """Generate a presigned URL for direct S3 upload from frontend."""
    bucket_name = get_bucket_name()
    key = f'videos/{uuid.uuid4()}/{file_name}'
    
    s3_client = get_s3_client()
    
    try:
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket_name,
                'Key': key,
                'ContentType': content_type
            },
            ExpiresIn=3600  # 1 hour
        )
        
        return {
            'upload_url': presigned_url,
            's3_uri': f's3://{bucket_name}/{key}',
            'key': key
        }
    except Exception as e:
        logger.error(f'Failed to generate presigned URL: {e}')
        raise ValueError(f'Failed to generate presigned URL: {str(e)}')


async def invoke_bedrock_data_automation(
    s3_uri: str, 
    project_arn: Optional[str] = None,
    output_s3_prefix: Optional[str] = None
) -> Dict[str, Any]:
    """
    Stage 1: Invoke Bedrock Data Automation with game analysis project.
    This processes the video and extracts structured sports data for any game type.
    Uses public default project to avoid managed profile restrictions with Lambda roles.
    """
    logger.info(f'Starting Data Automation analysis for video: {s3_uri}')
    
    # Get Data Automation configuration
    # Use custom project if provided, otherwise fall back to public default
    if not project_arn:
        project_arn = os.environ.get('DATA_AUTOMATION_PROJECT_ARN')
    
    logger.info(f'Project ARN: {project_arn}')
    
    # If still no project ARN, use public default project (works with Lambda roles)
    if not project_arn or project_arn == 'your-project-arn-here':
        region = get_region()
        project_arn = f'arn:aws:bedrock:{region}:aws:data-automation-project/public-default'
        logger.info(f'Using public default project: {project_arn}')
    
    logger.info(f'Project ARN 2: {project_arn}')

    # Generate unique job name
    job_name = f"game-analysis-{uuid.uuid4()}"
    bucket_name = get_bucket_name()
    output_prefix = output_s3_prefix or f"data-automation-results/{job_name}/"
    
    try:
        # Use Bedrock Data Automation Runtime client with correct API
        da_runtime_client = get_bedrock_data_automation_runtime_client()
        
        # Get profile ARN - required parameter
        profile_arn = get_profile_arn()
        
        logger.info(f'Input configurations: {s3_uri}')
        logger.info(f'output configurations: {f"s3://{bucket_name}/{output_prefix}"}')
        logger.info(f'Dataautomation configurations: {project_arn}')
        logger.info(f'dataAutomationProfileArn: {profile_arn}')

        # Start Data Automation job using correct API parameters
        # IMPORTANT: Parameter order matters! Must match MCP server working implementation
        response = da_runtime_client.invoke_data_automation_async(
            inputConfiguration={
                's3Uri': s3_uri
            },
            outputConfiguration={
                's3Uri': f"s3://{bucket_name}/{output_prefix}"
            },
            dataAutomationConfiguration={
                'dataAutomationProjectArn': project_arn
            },
            dataAutomationProfileArn=profile_arn
        )
        
        # Extract job information from response
        invocation_arn = response.get('invocationArn')
        logger.info(f'Data Automation invoked: {invocation_arn}')
        
        return {
            'invocationArn': invocation_arn,
            'status': 'STARTED',
            'outputS3Prefix': output_prefix,
            'projectArn': project_arn
        }
        
    except Exception as e:
        logger.error(f'Data Automation job failed to start: {e}')
        raise ValueError(f'Failed to start Data Automation: {str(e)}')


async def get_data_automation_job_status(job_arn: str) -> Dict[str, Any]:
    """Check the status of a Data Automation job."""
    try:
        da_client = get_bedrock_data_automation_client()
        
        response = da_client.get_data_automation_job(jobArn=job_arn)
        
        job_id = job_arn.split('/')[-1] if '/' in job_arn else job_arn
        
        return {
            'jobId': job_id,
            'jobArn': job_arn,
            'status': response.get('status'),
            'progress': response.get('progress', 0),
            'message': response.get('statusMessage', ''),
            'outputLocation': response.get('outputLocation')
        }
        
    except Exception as e:
        logger.error(f'Failed to get job status: {e}')
        job_id = job_arn.split('/')[-1] if '/' in job_arn else job_arn
        return {
            'jobId': job_id,
            'jobArn': job_arn,
            'status': 'UNKNOWN',
            'progress': 0,
            'message': f'Error: {str(e)}'
        }


async def get_data_automation_results(job_id: str, output_s3_prefix: str) -> Optional[Dict[str, Any]]:
    """Retrieve completed Data Automation results from S3."""
    try:
        s3_client = get_s3_client()
        bucket_name = get_bucket_name()
        
        # Try to get the structured output from Data Automation
        results_key = f"{output_s3_prefix}results.json"
        
        try:
            response = s3_client.get_object(Bucket=bucket_name, Key=results_key)
            content = response['Body'].read().decode('utf-8')
            da_results = json.loads(content)
            
            logger.info(f'Retrieved Data Automation results: {len(content)} characters')
            
            # Process and structure the game-specific data
            structured_results = process_game_data_automation_results(da_results)
            
            return structured_results
            
        except s3_client.exceptions.NoSuchKey:
            logger.warning(f'Data Automation results not found at {results_key}')
            return None
            
    except Exception as e:
        logger.error(f'Failed to retrieve Data Automation results: {e}')
        return None


def process_game_data_automation_results(da_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process Data Automation results into frontend-compatible format.
    Transforms Bedrock Data Automation output to match the frontend's AnalysisResult interface.
    
    Enhanced Frontend Format:
    {
        highlights: Array<{type, timestamp, endTimestamp, description, timecode, playerName, confidence}>,
        gameStats: {totalGoals, totalPenalties, keyPlayers, totalDuration, highlightsCount},
        scenes: Array<{type, startTime, endTime, description}>,
        gameContext: {location, atmosphere, advertisements},
        crowdReactions: Array<{type, timestamp, description, timecode}>,
        chapters: Array<{index, startTime, endTime, duration, summary}>,
        analysisConfidence: number,
        analysisTimestamp: string
    }
    """
    try:
        highlights = []
        scenes = []
        crowd_reactions = []
        chapter_summaries = []
        key_players = set()
        total_goals = 0
        total_penalties = 0
        total_duration = 0
        
        # Extract metadata from standardOutput
        standard_output = da_results.get('standardOutput', {})
        metadata = standard_output.get('metadata', {})
        total_duration = metadata.get('duration_millis', 0) / 1000  # Convert to seconds
        
        # Extract game context from customOutput (NEW)
        custom_output = da_results.get('customOutput', {})
        inference_result = custom_output.get('inference_result', {})
        
        game_location = inference_result.get('game_location', '')
        game_atmosphere = inference_result.get('game_atmosphere', '')
        advertisements_str = inference_result.get('advertisements', '')
        
        # Parse advertisements into array
        advertisements = []
        if advertisements_str:
            advertisements = [ad.strip() for ad in advertisements_str.split(',')]
        
        # Extract matched blueprint confidence
        matched_blueprint = custom_output.get('matched_blueprint', {})
        analysis_confidence = matched_blueprint.get('confidence', 1.0)
        
        # Process chapters from customOutput
        chapters = custom_output.get('chapters', [])
        
        for chapter in chapters:
            chapter_inference = chapter.get('inference_result', {})
            
            # Convert timestamps from milliseconds to seconds
            start_time = chapter.get('start_timestamp_millis', 0) / 1000
            end_time = chapter.get('end_timestamp_millis', 0) / 1000
            duration = chapter.get('duration_millis', 0) / 1000
            timecode = chapter.get('start_timecode_smpte', '00:00:00;00')
            chapter_index = chapter.get('chapter_index', 0)
            
            # Add chapter summary (NEW)
            chapter_summaries.append({
                'index': chapter_index,
                'startTime': start_time,
                'endTime': end_time,
                'duration': duration,
                'timecode': timecode,
                'summary': f"Chapter {chapter_index + 1}"
            })
            
            # Extract player actions (goals, saves, hits, etc.)
            player_actions = chapter_inference.get('player_actions', {})
            if player_actions and player_actions.get('action_type'):
                action_type = player_actions.get('action_type', '')
                player_name = player_actions.get('player_name', '')
                description = player_actions.get('description', '')
                
                # Skip empty or "Not applicable" entries
                if action_type and description and description != 'Not applicable':
                    highlights.append({
                        'type': f"player_{action_type}",
                        'timestamp': start_time,
                        'endTimestamp': end_time,
                        'description': description,
                        'timecode': timecode,
                        'playerName': player_name,
                        'confidence': 0.9
                    })
                    
                    # Track goals
                    if action_type.lower() == 'goal':
                        total_goals += 1
                    
                    # Track players
                    if player_name:
                        key_players.add(player_name)
            
            # Extract game events (celebrations, penalties, fights, etc.)
            game_events = chapter_inference.get('game_events', {})
            if game_events and game_events.get('event_type'):
                event_type = game_events.get('event_type', '')
                description = game_events.get('description', '')
                
                if event_type and description and description != 'Not applicable':
                    highlights.append({
                        'type': f"game_{event_type}",
                        'timestamp': start_time,
                        'endTimestamp': end_time,
                        'description': description,
                        'timecode': timecode,
                        'confidence': 0.9
                    })
                    
                    # Track goals from game events too
                    if event_type.lower() == 'goal':
                        total_goals += 1
            
            # Extract violations (penalties, fouls, etc.)
            violations = chapter_inference.get('violations', {})
            if violations and violations.get('violation_type'):
                violation_type = violations.get('violation_type', '')
                player_involved = violations.get('player_involved', '')
                description = violations.get('description', '')
                
                if violation_type and description and description != 'Not applicable':
                    highlights.append({
                        'type': f"violation_{violation_type}",
                        'timestamp': start_time,
                        'endTimestamp': end_time,
                        'description': description,
                        'timecode': timecode,
                        'playerName': player_involved,
                        'confidence': 0.85
                    })
                    total_penalties += 1
                    
                    if player_involved:
                        key_players.add(player_involved)
            
            # Extract crowd reactions (ENHANCED)
            spectator_reactions = chapter_inference.get('spectator_reactions', {})
            if spectator_reactions and spectator_reactions.get('reaction_type'):
                reaction_type = spectator_reactions.get('reaction_type', '')
                description = spectator_reactions.get('description', '')
                
                if reaction_type and description and description != 'Not applicable' and description:
                    # Add to crowd reactions array (NEW)
                    crowd_reactions.append({
                        'type': reaction_type,
                        'timestamp': start_time,
                        'endTimestamp': end_time,
                        'description': description,
                        'timecode': timecode
                    })
                    
                    # Also add to highlights for timeline
                    highlights.append({
                        'type': f"crowd_{reaction_type}",
                        'timestamp': start_time,
                        'endTimestamp': end_time,
                        'description': description,
                        'timecode': timecode,
                        'confidence': 0.8
                    })
            
            # Extract locker room scenes
            locker_scenes = chapter_inference.get('locker_room_scenes', {})
            if locker_scenes and locker_scenes.get('scene_type'):
                scene_type = locker_scenes.get('scene_type', '')
                description = locker_scenes.get('description', '')
                
                if scene_type and description and description != 'Not applicable':
                    scenes.append({
                        'type': f"locker_{scene_type}",
                        'startTime': start_time,
                        'endTime': end_time,
                        'description': description
                    })
                    
                    # Also add to highlights for timeline
                    highlights.append({
                        'type': f"scene_locker_{scene_type}",
                        'timestamp': start_time,
                        'endTimestamp': end_time,
                        'description': description,
                        'timecode': timecode,
                        'confidence': 0.85
                    })
            
            # Extract team bus scenes
            bus_scenes = chapter_inference.get('team_bus_scenes', {})
            if bus_scenes and bus_scenes.get('scene_type'):
                scene_type = bus_scenes.get('scene_type', '')
                description = bus_scenes.get('description', '')
                
                if scene_type and description and description != 'Not applicable':
                    scenes.append({
                        'type': f"bus_{scene_type}",
                        'startTime': start_time,
                        'endTime': end_time,
                        'description': description
                    })
                    
                    highlights.append({
                        'type': f"scene_bus_{scene_type}",
                        'timestamp': start_time,
                        'endTimestamp': end_time,
                        'description': description,
                        'timecode': timecode,
                        'confidence': 0.85
                    })
            
            # Extract off-field scenes
            off_field_scenes = chapter_inference.get('off_field_scenes', {})
            if off_field_scenes and off_field_scenes.get('scene_type'):
                scene_type = off_field_scenes.get('scene_type', '')
                description = off_field_scenes.get('description', '')
                
                if scene_type and description and description != 'Not applicable':
                    scenes.append({
                        'type': scene_type,
                        'startTime': start_time,
                        'endTime': end_time,
                        'description': description
                    })
        
        # Sort highlights by timestamp
        highlights.sort(key=lambda x: x.get('timestamp', 0))
        
        # Sort crowd reactions by timestamp
        crowd_reactions.sort(key=lambda x: x.get('timestamp', 0))
        
        # Sort chapters by index
        chapter_summaries.sort(key=lambda x: x.get('index', 0))
        
        # Build enhanced result matching frontend interface
        result = {
            'highlights': highlights,
            'gameStats': {
                'totalGoals': total_goals,
                'totalPenalties': total_penalties,
                'keyPlayers': list(key_players),
                'totalDuration': total_duration,
                'highlightsCount': len(highlights)
            },
            'scenes': scenes,
            'gameContext': {
                'location': game_location,
                'atmosphere': game_atmosphere,
                'advertisements': advertisements
            },
            'crowdReactions': crowd_reactions,
            'chapters': chapter_summaries,
            'analysisConfidence': analysis_confidence,
            'analysisTimestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f'Processed game analysis: {len(highlights)} highlights, '
                   f'{total_goals} goals, {total_penalties} penalties, '
                   f'{len(key_players)} key players, {len(scenes)} scenes, '
                   f'{len(crowd_reactions)} crowd reactions, {len(chapter_summaries)} chapters')
        
        return result
        
    except Exception as e:
        logger.error(f'Failed to process game Data Automation results: {e}')
        return {
            'highlights': [],
            'gameStats': {
                'totalGoals': 0,
                'totalPenalties': 0,
                'keyPlayers': [],
                'totalDuration': 0,
                'highlightsCount': 0
            },
            'scenes': [],
            'analysisTimestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }


async def invoke_agent_with_structured_context(
    question: str, 
    structured_data: Dict[str, Any], 
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Stage 2: Invoke Bedrock Agent with structured Data Automation context.
    This provides intelligent Q&A based on factual hockey data.
    """
    logger.info(f'Invoking Agent with structured context for question: {question}')
    
    # Get Bedrock Agent configuration
    agent_id = os.environ.get('BEDROCK_AGENT_ID')
    agent_alias_id = os.environ.get('BEDROCK_AGENT_ALIAS_ID')
    
    if not agent_id or not agent_alias_id:
        raise ValueError('BEDROCK_AGENT_ID and BEDROCK_AGENT_ALIAS_ID must be set in environment variables')
    
    # Build structured context from Data Automation results
    context = build_hockey_context_for_agent(structured_data, question)
    
    # Create enhanced prompt with structured context
    enhanced_prompt = f"""
Hockey Game Analysis Context:
{context}

User Question: {question}

Please answer the question based on the structured game analysis data provided above. 
Include specific timestamps, player names, and confidence scores when available.
If the data doesn't contain relevant information for the question, please indicate that clearly.
"""
    
    try:
        runtime_client = get_bedrock_agent_runtime_client()
        
        response = runtime_client.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=session_id or str(uuid.uuid4()),
            inputText=enhanced_prompt
        )
        
        # Process the streaming response
        answer_text = ""
        for event in response.get('completion', []):
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    answer_text += chunk['bytes'].decode('utf-8')
        
        # Extract relevant information from structured data
        relevant_timestamps = extract_relevant_timestamps(structured_data, question)
        related_players = extract_related_players(structured_data, question)
        
        return {
            'answer': answer_text,
            'confidence': 0.9,
            'relevant_timestamps': relevant_timestamps,
            'related_players': related_players,
            'sources': ['data_automation', 'bedrock_agent'],
            'structured_context_used': True
        }
        
    except Exception as e:
        logger.error(f'Agent invocation with context failed: {e}')
        raise ValueError(f'Agent Q&A failed: {str(e)}')


def build_hockey_context_for_agent(structured_data: Dict[str, Any], question: str) -> str:
    """Build contextual information for the Agent based on structured hockey data."""
    context_parts = []
    
    # Add game events context
    game_events = structured_data.get('game_events', [])
    if game_events:
        context_parts.append(f"Game Events ({len(game_events)} total):")
        for event in game_events[:5]:  # Top 5 events
            context_parts.append(f"- {event.get('event')} at {event.get('timestamp')}: {event.get('description')}")
    
    # Add player actions context
    player_actions = structured_data.get('player_actions', [])
    if player_actions:
        context_parts.append(f"\nPlayer Actions ({len(player_actions)} total):")
        for action in player_actions[:5]:  # Top 5 actions
            context_parts.append(f"- {action.get('player')} {action.get('action')} at {action.get('timestamp')}")
    
    # Add game context
    game_context = structured_data.get('game_context', {})
    if game_context:
        context_parts.append(f"\nGame Context:")
        if game_context.get('location'):
            context_parts.append(f"- Location: {game_context['location']}")
        if game_context.get('atmosphere'):
            context_parts.append(f"- Atmosphere: {game_context['atmosphere']}")
    
    # Add metadata
    metadata = structured_data.get('metadata', {})
    if metadata:
        context_parts.append(f"\nAnalysis Metadata:")
        context_parts.append(f"- Total Chapters: {metadata.get('total_chapters', 0)}")
        context_parts.append(f"- Blueprint Confidence: {metadata.get('confidence', 0.9)}")
    
    return '\n'.join(context_parts)


def extract_relevant_timestamps(structured_data: Dict[str, Any], question: str) -> List[Dict[str, Any]]:
    """Extract timestamps relevant to the user's question."""
    relevant_timestamps = []
    question_lower = question.lower()
    
    # Check game events for relevance
    for event in structured_data.get('game_events', []):
        event_text = f"{event.get('event', '')} {event.get('description', '')}".lower()
        if any(word in event_text for word in question_lower.split()):
            relevant_timestamps.append({
                'timestamp': event.get('timestamp'),
                'description': f"{event.get('event')}: {event.get('description')}",
                'relevance': 0.9
            })
    
    # Check player actions for relevance
    for action in structured_data.get('player_actions', []):
        action_text = f"{action.get('player', '')} {action.get('action', '')}".lower()
        if any(word in action_text for word in question_lower.split()):
            relevant_timestamps.append({
                'timestamp': action.get('timestamp'),
                'description': f"{action.get('player')} {action.get('action')}",
                'relevance': 0.8
            })
    
    return relevant_timestamps[:5]  # Limit to 5 most relevant


def extract_related_players(structured_data: Dict[str, Any], question: str) -> List[str]:
    """Extract player names related to the user's question."""
    related_players = set()
    question_lower = question.lower()
    
    # Extract players from actions
    for action in structured_data.get('player_actions', []):
        player_name = action.get('player', '')
        action_text = f"{player_name} {action.get('action', '')}".lower()
        
        if any(word in action_text for word in question_lower.split()) or any(word in question_lower for word in player_name.lower().split()):
            related_players.add(player_name)
    
    return list(related_players)


# Legacy function for backward compatibility - now implements proper two-stage flow
async def invoke_data_automation_and_get_results(
    s3_uri: str, project_arn: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Legacy function that now implements the proper Data Automation → Agent flow.
    
    Stage 1: Data Automation with hockey blueprint
    Stage 2: Return structured results for Agent Q&A
    """
    logger.info(f'Starting two-stage analysis for video: {s3_uri}')
    
    try:
        # First try the real Bedrock Data Automation
        try:
            # Stage 1: Start Data Automation job
            da_job = await invoke_bedrock_data_automation(s3_uri, project_arn)
            invocation_arn = da_job['invocationArn']
            
            # Poll for completion (in production, use async processing)
            max_wait_time = 1800  # 30 minutes
            poll_interval = 30    # 30 seconds
            elapsed_time = 0
            
            # Use the runtime client to check status
            da_runtime_client = get_bedrock_data_automation_runtime_client()
            
            while elapsed_time < max_wait_time:
                await asyncio.sleep(poll_interval)
                elapsed_time += poll_interval
                
                # Log progress
                logger.info(f'Polling Data Automation status... ({elapsed_time}s / {max_wait_time}s elapsed)')
                
                # Check status using invocation ARN
                get_response = da_runtime_client.get_data_automation_status(invocationArn=invocation_arn)
                status = get_response.get('status')
                
                logger.info(f'Current status: {status}')
                
                if status == 'Success':
                    # Stage 2: Get structured results
                    output_uri = get_response.get('outputConfiguration', {}).get('s3Uri')
                    if not output_uri:
                        raise ValueError('Data Automation completed but no output URI found')
                    
                    # Download job metadata
                    job_metadata = await download_from_s3(output_uri)
                    
                    # Extract output paths
                    standard_output_uri = None
                    custom_output_uri = None
                    
                    if job_metadata:
                        try:
                            standard_output_uri = job_metadata['output_metadata'][0]['segment_metadata'][0].get('standard_output_path')
                        except (KeyError, IndexError):
                            pass
                        
                        try:
                            custom_output_uri = job_metadata['output_metadata'][0]['segment_metadata'][0].get('custom_output_path')
                        except (KeyError, IndexError):
                            pass
                    
                    if not standard_output_uri and not custom_output_uri:
                        raise ValueError('Data Automation completed but no output files found')
                    
                    # Download results
                    results = {}
                    if standard_output_uri:
                        standard_output = await download_from_s3(standard_output_uri)
                        if standard_output:
                            results['standardOutput'] = standard_output
                    
                    if custom_output_uri:
                        custom_output = await download_from_s3(custom_output_uri)
                        if custom_output:
                            results['customOutput'] = custom_output
                    
                    logger.info('Two-stage analysis completed successfully')
                    return results
                        
                elif status in ['Failed', 'Cancelled']:
                    error_msg = get_response.get('errorMessage', 'Unknown error')
                    raise ValueError(f"Data Automation job {status}: {error_msg}")
                
                elif status != 'InProgress':
                    logger.warning(f'Unexpected status: {status}')
            
            # Timeout
            raise ValueError(f'Data Automation job timed out after {max_wait_time} seconds')
            
        except Exception as da_error:
            logger.error(f'Bedrock Data Automation failed: {da_error}')
            # NO FALLBACK - Fail properly when AWS services are not available
            raise ValueError(f'Bedrock Data Automation failed: {str(da_error)}')
        
    except Exception as e:
        logger.error(f'Two-stage analysis failed: {e}')
        raise ValueError(f'Analysis failed: {str(e)}')


async def list_bedrock_projects() -> list:
    """List all Bedrock Agents."""
    client = get_bedrock_data_automation_client()
    try:
        response = client.list_agents()
        agents = response.get('agentSummaries', [])
        
        # Convert agent summaries to project-like format
        projects = []
        for agent in agents:
            projects.append({
                'projectArn': f"arn:aws:bedrock:{get_region()}:{get_account_id()}:agent/{agent.get('agentId', '')}",
                'projectName': agent.get('agentName', 'Unknown Agent'),
                'description': agent.get('description', 'Bedrock Agent for gameplay analysis'),
                'status': agent.get('agentStatus', 'UNKNOWN')
            })
        
        return projects
    except Exception as e:
        logger.error(f'Failed to list Bedrock agents: {e}')
        # Return configured agent as fallback
        agent_id = os.environ.get('BEDROCK_AGENT_ID')
        if agent_id:
            return [{
                'projectArn': f"arn:aws:bedrock:{get_region()}:{get_account_id()}:agent/{agent_id}",
                'projectName': 'Configured Gameplay Analysis Agent',
                'description': 'Pre-configured Bedrock Agent for gameplay analysis',
                'status': 'ACTIVE'
            }]
        return []


async def get_bedrock_project(project_arn: str) -> Dict[str, Any]:
    """Get details of a Bedrock Agent."""
    client = get_bedrock_data_automation_client()
    
    # Extract agent ID from ARN
    agent_id = project_arn.split('/')[-1] if '/' in project_arn else project_arn
    
    try:
        response = client.get_agent(agentId=agent_id)
        agent = response.get('agent', {})
        
        return {
            'projectArn': project_arn,
            'projectName': agent.get('agentName', 'Unknown Agent'),
            'description': agent.get('description', 'Bedrock Agent for gameplay analysis'),
            'status': agent.get('agentStatus', 'UNKNOWN'),
            'agentId': agent.get('agentId'),
            'foundationModel': agent.get('foundationModel')
        }
    except Exception as e:
        logger.error(f'Failed to get Bedrock agent details: {e}')
        # Return fallback info
        return {
            'projectArn': project_arn,
            'projectName': 'Gameplay Analysis Agent',
            'description': 'Bedrock Agent for gameplay analysis',
            'status': 'ACTIVE'
        }


async def verify_data_automation_permissions() -> Dict[str, Any]:
    """
    Verify that Bedrock Data Automation has proper permissions.
    Returns diagnostic information about the current setup.
    """
    logger.info('Verifying Bedrock Data Automation permissions...')
    
    verification_results = {
        'iam_role_exists': False,
        'iam_role_arn': None,
        'iam_role_policies': [],
        's3_bucket_exists': False,
        's3_bucket_name': None,
        's3_bucket_policy': None,
        'data_automation_project_exists': False,
        'data_automation_project_arn': None,
        'permissions_issues': [],
        'recommendations': []
    }
    
    try:
        # Check IAM role
        session = get_aws_session()
        iam_client = session.client('iam', region_name=get_region())
        
        try:
            role_response = iam_client.get_role(RoleName='BedrockDataAutomationExecutionRole')
            verification_results['iam_role_exists'] = True
            verification_results['iam_role_arn'] = role_response['Role']['Arn']
            
            # Get role policies
            policies_response = iam_client.list_role_policies(RoleName='BedrockDataAutomationExecutionRole')
            verification_results['iam_role_policies'] = policies_response.get('PolicyNames', [])
            
        except iam_client.exceptions.NoSuchEntityException:
            verification_results['permissions_issues'].append('BedrockDataAutomationExecutionRole does not exist')
            verification_results['recommendations'].append('Run deployment script to create the IAM role')
        
        # Check S3 bucket
        bucket_name = get_bucket_name()
        if bucket_name:
            s3_client = get_s3_client()
            
            try:
                s3_client.head_bucket(Bucket=bucket_name)
                verification_results['s3_bucket_exists'] = True
                verification_results['s3_bucket_name'] = bucket_name
                
                # Try to get bucket policy
                try:
                    policy_response = s3_client.get_bucket_policy(Bucket=bucket_name)
                    verification_results['s3_bucket_policy'] = 'exists'
                except s3_client.exceptions.NoSuchBucketPolicy:
                    verification_results['s3_bucket_policy'] = 'missing'
                    verification_results['permissions_issues'].append('S3 bucket policy is missing')
                    verification_results['recommendations'].append('Update S3 bucket policy to allow Bedrock Data Automation access')
                    
            except Exception as e:
                verification_results['permissions_issues'].append(f'S3 bucket {bucket_name} is not accessible: {str(e)}')
        
        # Check Data Automation project
        project_arn = os.environ.get('DATA_AUTOMATION_PROJECT_ARN')
        if project_arn and project_arn != 'your-project-arn-here':
            try:
                da_client = get_bedrock_data_automation_client()
                project_response = da_client.get_data_automation_project(projectArn=project_arn)
                verification_results['data_automation_project_exists'] = True
                verification_results['data_automation_project_arn'] = project_arn
                
            except Exception as e:
                verification_results['permissions_issues'].append(f'Data Automation project not accessible: {str(e)}')
                verification_results['recommendations'].append('Verify Data Automation project ARN in environment variables')
        else:
            verification_results['permissions_issues'].append('Data Automation project ARN not configured')
            verification_results['recommendations'].append('Set DATA_AUTOMATION_PROJECT_ARN in environment variables')
        
        # Overall assessment
        if not verification_results['permissions_issues']:
            verification_results['status'] = 'HEALTHY'
        elif len(verification_results['permissions_issues']) <= 2:
            verification_results['status'] = 'NEEDS_ATTENTION'
        else:
            verification_results['status'] = 'CRITICAL'
        
        return verification_results
        
    except Exception as e:
        logger.error(f'Failed to verify Data Automation permissions: {e}')
        verification_results['permissions_issues'].append(f'Verification failed: {str(e)}')
        verification_results['status'] = 'ERROR'
        return verification_results


async def fix_data_automation_permissions() -> Dict[str, Any]:
    """
    Attempt to fix common Bedrock Data Automation permission issues.
    Returns the results of the fix attempts.
    """
    logger.info('Attempting to fix Bedrock Data Automation permissions...')
    
    fix_results = {
        'actions_taken': [],
        'errors': [],
        'success': False
    }
    
    try:
        # First, verify current state
        verification = await verify_data_automation_permissions()
        
        session = get_aws_session()
        iam_client = session.client('iam', region_name=get_region())
        account_id = get_account_id()
        region = get_region()
        bucket_name = get_bucket_name()
        
        # Fix IAM role if needed
        if not verification['iam_role_exists']:
            try:
                # Create trust policy
                trust_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {
                                "Service": "bedrock.amazonaws.com"
                            },
                            "Action": "sts:AssumeRole",
                            "Condition": {
                                "StringEquals": {
                                    "aws:SourceAccount": account_id
                                }
                            }
                        }
                    ]
                }
                
                # Create role
                iam_client.create_role(
                    RoleName='BedrockDataAutomationExecutionRole',
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description='IAM role for Bedrock Data Automation to access S3 bucket and CloudWatch'
                )
                
                fix_results['actions_taken'].append('Created BedrockDataAutomationExecutionRole')
                
            except Exception as e:
                fix_results['errors'].append(f'Failed to create IAM role: {str(e)}')
        
        # Update IAM role policies
        if verification['iam_role_exists'] or 'Created BedrockDataAutomationExecutionRole' in fix_results['actions_taken']:
            try:
                # Create comprehensive policy
                policy_document = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "S3BucketAccess",
                            "Effect": "Allow",
                            "Action": [
                                "s3:GetObject",
                                "s3:GetObjectVersion",
                                "s3:PutObject",
                                "s3:PutObjectAcl",
                                "s3:DeleteObject",
                                "s3:ListBucket",
                                "s3:GetBucketLocation",
                                "s3:GetBucketVersioning"
                            ],
                            "Resource": [
                                f"arn:aws:s3:::{bucket_name}",
                                f"arn:aws:s3:::{bucket_name}/*"
                            ]
                        },
                        {
                            "Sid": "CloudWatchLogsAccess",
                            "Effect": "Allow",
                            "Action": [
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                                "logs:DescribeLogGroups",
                                "logs:DescribeLogStreams"
                            ],
                            "Resource": f"arn:aws:logs:{region}:{account_id}:*"
                        },
                        {
                            "Sid": "BedrockDataAutomationAccess",
                            "Effect": "Allow",
                            "Action": [
                                "bedrock:InvokeModel",
                                "bedrock:GetFoundationModel",
                                "bedrock:ListFoundationModels"
                            ],
                            "Resource": "*"
                        }
                    ]
                }
                
                iam_client.put_role_policy(
                    RoleName='BedrockDataAutomationExecutionRole',
                    PolicyName='BedrockDataAutomationComprehensiveAccess',
                    PolicyDocument=json.dumps(policy_document)
                )
                
                fix_results['actions_taken'].append('Updated IAM role policies')
                
            except Exception as e:
                fix_results['errors'].append(f'Failed to update IAM role policies: {str(e)}')
        
        # Fix S3 bucket policy if needed
        if verification['s3_bucket_exists'] and verification['s3_bucket_policy'] == 'missing':
            try:
                s3_client = get_s3_client()
                
                bucket_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "AllowBedrockDataAutomationRole",
                            "Effect": "Allow",
                            "Principal": {
                                "AWS": f"arn:aws:iam::{account_id}:role/BedrockDataAutomationExecutionRole"
                            },
                            "Action": [
                                "s3:GetObject",
                                "s3:GetObjectVersion",
                                "s3:PutObject",
                                "s3:PutObjectAcl",
                                "s3:DeleteObject",
                                "s3:ListBucket",
                                "s3:GetBucketLocation",
                                "s3:GetBucketVersioning"
                            ],
                            "Resource": [
                                f"arn:aws:s3:::{bucket_name}",
                                f"arn:aws:s3:::{bucket_name}/*"
                            ]
                        },
                        {
                            "Sid": "AllowBedrockServices",
                            "Effect": "Allow",
                            "Principal": {
                                "Service": [
                                    "bedrock.amazonaws.com",
                                    "bedrock-data-automation.amazonaws.com"
                                ]
                            },
                            "Action": [
                                "s3:GetObject",
                                "s3:GetObjectVersion",
                                "s3:PutObject",
                                "s3:PutObjectAcl",
                                "s3:ListBucket",
                                "s3:GetBucketLocation"
                            ],
                            "Resource": [
                                f"arn:aws:s3:::{bucket_name}",
                                f"arn:aws:s3:::{bucket_name}/*"
                            ],
                            "Condition": {
                                "StringEquals": {
                                    "aws:SourceAccount": account_id
                                }
                            }
                        }
                    ]
                }
                
                s3_client.put_bucket_policy(
                    Bucket=bucket_name,
                    Policy=json.dumps(bucket_policy)
                )
                
                fix_results['actions_taken'].append('Updated S3 bucket policy')
                
            except Exception as e:
                fix_results['errors'].append(f'Failed to update S3 bucket policy: {str(e)}')
        
        # Determine overall success
        fix_results['success'] = len(fix_results['actions_taken']) > 0 and len(fix_results['errors']) == 0
        
        if fix_results['success']:
            logger.info('Successfully fixed Bedrock Data Automation permissions')
        else:
            logger.warning(f'Permission fix completed with {len(fix_results["errors"])} errors')
        
        return fix_results
        
    except Exception as e:
        logger.error(f'Failed to fix Data Automation permissions: {e}')
        fix_results['errors'].append(f'Fix operation failed: {str(e)}')
        return fix_results


async def test_data_automation_access(s3_uri: str) -> Dict[str, Any]:
    """
    Test Bedrock Data Automation access by attempting a minimal operation.
    This helps verify that permissions are working correctly.
    """
    logger.info(f'Testing Bedrock Data Automation access with S3 URI: {s3_uri}')
    
    test_results = {
        'access_test_passed': False,
        'error_message': None,
        'recommendations': []
    }
    
    try:
        # Get Data Automation configuration
        project_arn = os.environ.get('DATA_AUTOMATION_PROJECT_ARN')
        profile_arn = get_profile_arn()
        
        if not project_arn or project_arn == 'your-project-arn-here':
            test_results['error_message'] = 'DATA_AUTOMATION_PROJECT_ARN not configured'
            test_results['recommendations'].append('Set DATA_AUTOMATION_PROJECT_ARN in environment variables')
            return test_results
        
        # Test basic S3 access first
        bucket, key = get_bucket_and_key_from_s3_uri(s3_uri)
        s3_client = get_s3_client()
        
        try:
            s3_client.head_object(Bucket=bucket, Key=key)
        except Exception as e:
            test_results['error_message'] = f'S3 object not accessible: {str(e)}'
            test_results['recommendations'].append('Verify S3 object exists and is accessible')
            return test_results
        
        # Test Data Automation API access
        try:
            da_runtime_client = get_bedrock_data_automation_runtime_client()
            
            # Generate unique job name for test
            test_job_name = f"access-test-{uuid.uuid4()}"
            bucket_name = get_bucket_name()
            output_prefix = f"test-results/{test_job_name}/"
            
            # Attempt to start a Data Automation job (this will test permissions)
            response = da_runtime_client.invoke_data_automation_async(
                inputConfiguration={
                    's3Uri': s3_uri
                },
                outputConfiguration={
                    's3Uri': f"s3://{bucket_name}/{output_prefix}"
                },
                dataAutomationProfileArn=profile_arn,
                dataAutomationConfiguration={
                    'dataAutomationProjectArn': project_arn
                } if project_arn else {}
            )
            
            # If we get here, the API call succeeded
            job_arn = response.get('jobArn')
            test_results['access_test_passed'] = True
            test_results['test_job_arn'] = job_arn
            
            logger.info(f'Data Automation access test passed. Test job ARN: {job_arn}')
            
            # Optionally cancel the test job to avoid unnecessary processing
            try:
                da_client = get_bedrock_data_automation_client()
                da_client.stop_data_automation_job(jobArn=job_arn)
                logger.info('Cancelled test job to avoid unnecessary processing')
            except Exception:
                pass  # Ignore cancellation errors
            
        except Exception as e:
            error_str = str(e)
            test_results['error_message'] = f'Data Automation API call failed: {error_str}'
            
            if 'AccessDenied' in error_str:
                test_results['recommendations'].extend([
                    'Check IAM role permissions for Bedrock Data Automation',
                    'Verify S3 bucket policy allows Bedrock service access',
                    'Ensure Data Automation project has correct execution role assigned'
                ])
            elif 'InvalidParameter' in error_str:
                test_results['recommendations'].extend([
                    'Verify Data Automation project ARN is correct',
                    'Check S3 URI format and accessibility'
                ])
            else:
                test_results['recommendations'].append('Run permission verification and fix operations')
        
        return test_results
        
    except Exception as e:
        logger.error(f'Data Automation access test failed: {e}')
        test_results['error_message'] = f'Access test failed: {str(e)}'
        return test_results
