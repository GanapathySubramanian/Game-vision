"""
Lambda function for Query Interface Action Group.
Handles natural language queries about analyzed video content.
"""

import json
import os
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
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
        get_bedrock_agent_runtime_client
    )
except ImportError:
    # Fall back to local import from shared directory
    from shared.aws_helpers import (
        get_bedrock_agent_runtime_client
    )


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for query interface operations.
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Extract the action group, API path, and HTTP method
        action_group = event.get('actionGroup', '')
        api_path = event.get('apiPath', '')
        http_method = event.get('httpMethod', '')
        
        # Extract session attributes (contains videoId)
        session_attributes = event.get('sessionAttributes', {})
        video_id = session_attributes.get('videoId', '')
        
        logger.info(f"Session attributes: {session_attributes}")
        logger.info(f"Extracted videoId from session: {video_id}")
        
        # Extract parameters from the event
        parameters = {}
        if 'parameters' in event:
            for param in event['parameters']:
                parameters[param['name']] = param['value']
        
        # Extract request body if present - properties is a LIST, not a dict!
        request_body = {}
        if 'requestBody' in event and 'content' in event['requestBody']:
            content = event['requestBody']['content']
            if 'application/json' in content:
                # Parse the properties list into a dictionary
                properties = content['application/json'].get('properties', [])
                for prop in properties:
                    if isinstance(prop, dict):
                        request_body[prop.get('name')] = prop.get('value')
        
        # Override videoId from session attributes (more reliable than parameters)
        if video_id:
            request_body['videoId'] = video_id
            parameters['videoId'] = video_id
        
        logger.info(f"Parsed request_body: {request_body}")
        logger.info(f"Parsed parameters: {parameters}")
        
        # Route to appropriate handler based on API path
        if api_path == '/ask-question' and http_method == 'POST':
            return handle_ask_question(request_body, api_path, http_method, event)
        elif api_path == '/get-video-summary' and http_method == 'GET':
            return handle_get_video_summary(parameters, api_path, http_method, event)
        elif api_path == '/search-content' and http_method == 'POST':
            return handle_search_content(request_body, api_path, http_method, event)
        else:
            return create_error_response(f"Unknown API path: {api_path}", api_path, http_method)
            
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}", exc_info=True)
        return create_error_response(str(e), event.get('apiPath', ''), event.get('httpMethod', ''))


def handle_ask_question(request_body: Dict[str, Any], api_path: str, http_method: str, event: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Process natural language questions about video content.
    Simply retrieves the analysis JSON and passes it to the Agent for intelligent parsing.
    """
    try:
        video_id = request_body.get('videoId')
        question = request_body.get('question')
        
        if not video_id or not question:
            return create_error_response("videoId and question are required", api_path, http_method)
        
        # Get analysis results for the video
        analysis_results = get_analysis_from_db(video_id)
        
        if not analysis_results:
            return create_error_response(f"No analysis results found for video {video_id}", api_path, http_method)
        
        logger.info(f"Retrieved analysis data with {len(str(analysis_results))} characters")
        
        # Simply return the full analysis data - let the Bedrock Agent (LLM) parse it intelligently
        # The Agent can understand the JSON structure and extract relevant information
        response_body = {
            'videoId': video_id,
            'question': question,
            'analysisData': analysis_results,
            'message': 'Analysis data retrieved successfully. The Agent will process this data to answer your question.',
            'dataStructure': {
                'matched_blueprint': 'Blueprint information and confidence score',
                'inference_result': 'Overall game context (location, atmosphere, advertisements)',
                'chapters': 'Array of video chapters with player actions, game events, spectator reactions, and locker room scenes'
            }
        }
        
        return create_success_response(response_body, api_path, http_method)
        
    except Exception as e:
        logger.error(f"Error in handle_ask_question: {str(e)}")
        return create_error_response(str(e), api_path, http_method)


def handle_get_video_summary(parameters: Dict[str, Any], api_path: str, http_method: str) -> Dict[str, Any]:
    """
    Retrieve a comprehensive summary of the analyzed video.
    """
    try:
        video_id = parameters.get('videoId')
        summary_type = parameters.get('summaryType', 'detailed')
        
        if not video_id:
            return create_error_response("videoId is required", api_path, http_method)
        
        # Get analysis results for the video
        analysis_results = get_analysis_from_db(video_id)
        
        if not analysis_results:
            return create_error_response(f"No analysis results found for video {video_id}", api_path, http_method)
        
        # Generate summary based on type
        summary_data = generate_comprehensive_summary(analysis_results, summary_type)
        
        response_body = {
            'videoId': video_id,
            'title': summary_data['title'],
            'summary': summary_data['summary'],
            'keyMoments': summary_data['key_moments'],
            'playerStats': summary_data['player_stats'],
            'gameContext': summary_data['game_context'],
            'duration': summary_data['duration']
        }
        
        return create_success_response(response_body, api_path, http_method)
        
    except Exception as e:
        logger.error(f"Error in handle_get_video_summary: {str(e)}")
        return create_error_response(str(e), api_path, http_method)


def handle_search_content(request_body: Dict[str, Any], api_path: str, http_method: str) -> Dict[str, Any]:
    """
    Search for specific content within the analyzed video.
    """
    try:
        video_id = request_body.get('videoId')
        search_query = request_body.get('searchQuery')
        search_type = request_body.get('searchType', 'all')
        time_range = request_body.get('timeRange', {})
        
        if not video_id or not search_query:
            return create_error_response("videoId and searchQuery are required", api_path, http_method)
        
        # Get analysis results for the video
        analysis_results = get_analysis_from_db(video_id)
        
        if not analysis_results:
            return create_error_response(f"No analysis results found for video {video_id}", api_path, http_method)
        
        # Perform search
        search_results = search_video_content(
            analysis_results, 
            search_query, 
            search_type, 
            time_range
        )
        
        response_body = {
            'videoId': video_id,
            'searchQuery': search_query,
            'results': search_results['results'],
            'totalResults': search_results['total'],
            'searchTime': search_results['search_time']
        }
        
        return create_success_response(response_body, api_path, http_method)
        
    except Exception as e:
        logger.error(f"Error in handle_search_content: {str(e)}")
        return create_error_response(str(e), api_path, http_method)


def process_question_with_analysis(
    question: str, 
    analysis_results: Dict[str, Any], 
    context: str, 
    response_format: str
) -> Dict[str, Any]:
    """
    Process a natural language question using analysis results.
    """
    try:
        # Initialize response data
        answer_data = {
            'answer': '',
            'confidence': 0.0,
            'timestamps': [],
            'players': [],
            'sources': []
        }
        
        # Normalize question for analysis
        question_lower = question.lower()
        
        # Extract relevant data from analysis results
        custom_output = analysis_results.get('customOutput', {})
        standard_output = analysis_results.get('standardOutput', {})
        
        # Question type detection and processing
        if any(word in question_lower for word in ['goal', 'score', 'scored']):
            answer_data = process_goal_question(question, custom_output, standard_output)
        elif any(word in question_lower for word in ['player', 'who']):
            answer_data = process_player_question(question, custom_output, standard_output)
        elif any(word in question_lower for word in ['when', 'time', 'timestamp']):
            answer_data = process_time_question(question, custom_output, standard_output)
        elif any(word in question_lower for word in ['summary', 'what happened', 'overview']):
            answer_data = process_summary_question(question, custom_output, standard_output)
        else:
            # General question processing
            answer_data = process_general_question(question, custom_output, standard_output)
        
        # Adjust response based on format preference
        if response_format == 'summary':
            answer_data['answer'] = summarize_answer(answer_data['answer'])
        elif response_format == 'timestamps':
            answer_data['answer'] = format_answer_with_timestamps(answer_data)
        
        return answer_data
        
    except Exception as e:
        logger.error(f"Error processing question: {str(e)}")
        return {
            'answer': 'I encountered an error while processing your question.',
            'confidence': 0.0,
            'timestamps': [],
            'players': [],
            'sources': []
        }


def process_goal_question(question: str, custom_output: Dict, standard_output: Dict) -> Dict[str, Any]:
    """Process questions about goals and scoring."""
    answer_data = {
        'answer': '',
        'confidence': 0.8,
        'timestamps': [],
        'players': [],
        'sources': ['custom_analysis']
    }
    
    goals = []
    if 'player_actions' in custom_output:
        for action in custom_output['player_actions']:
            if 'goal' in action.get('action', '').lower():
                goals.append(action)
                answer_data['players'].append(action.get('player', ''))
                answer_data['timestamps'].append({
                    'timestamp': action.get('timestamp', ''),
                    'description': f"{action.get('player', '')} scored",
                    'relevance': 1.0
                })
    
    if goals:
        goal_descriptions = []
        for goal in goals:
            player = goal.get('player', 'Unknown player')
            timestamp = goal.get('timestamp', 'Unknown time')
            goal_descriptions.append(f"{player} scored at {timestamp}")
        
        answer_data['answer'] = f"Goals in this video: {'; '.join(goal_descriptions)}"
    else:
        answer_data['answer'] = "No goals were detected in this video analysis."
        answer_data['confidence'] = 0.6
    
    return answer_data


def process_player_question(question: str, custom_output: Dict, standard_output: Dict) -> Dict[str, Any]:
    """Process questions about specific players."""
    answer_data = {
        'answer': '',
        'confidence': 0.7,
        'timestamps': [],
        'players': [],
        'sources': ['custom_analysis']
    }
    
    # Extract player names from the question
    question_words = question.split()
    potential_players = []
    
    # Look for capitalized words that might be player names
    for word in question_words:
        if word[0].isupper() and len(word) > 2:
            potential_players.append(word)
    
    player_actions = []
    if 'player_actions' in custom_output:
        for action in custom_output['player_actions']:
            player_name = action.get('player', '')
            # Check if any potential player names match
            if any(name.lower() in player_name.lower() for name in potential_players):
                player_actions.append(action)
                answer_data['players'].append(player_name)
                answer_data['timestamps'].append({
                    'timestamp': action.get('timestamp', ''),
                    'description': f"{player_name} {action.get('action', '')}",
                    'relevance': 0.9
                })
    
    if player_actions:
        action_descriptions = []
        for action in player_actions:
            player = action.get('player', '')
            action_type = action.get('action', '')
            timestamp = action.get('timestamp', '')
            action_descriptions.append(f"{player} {action_type} at {timestamp}")
        
        answer_data['answer'] = f"Player actions found: {'; '.join(action_descriptions)}"
    else:
        answer_data['answer'] = "No specific player actions found matching your query."
        answer_data['confidence'] = 0.4
    
    return answer_data


def process_time_question(question: str, custom_output: Dict, standard_output: Dict) -> Dict[str, Any]:
    """Process questions about timing and timestamps."""
    answer_data = {
        'answer': '',
        'confidence': 0.6,
        'timestamps': [],
        'players': [],
        'sources': ['standard_analysis', 'custom_analysis']
    }
    
    # Collect all timestamped events
    events = []
    
    # From custom output
    if 'player_actions' in custom_output:
        for action in custom_output['player_actions']:
            events.append({
                'timestamp': action.get('timestamp', ''),
                'description': f"{action.get('player', '')} {action.get('action', '')}",
                'type': 'player_action'
            })
    
    # From standard output
    if 'chapters' in standard_output:
        for chapter in standard_output['chapters']:
            events.append({
                'timestamp': chapter.get('start_timestamp', ''),
                'description': chapter.get('title', ''),
                'type': 'chapter'
            })
    
    # Sort events by timestamp
    events.sort(key=lambda x: x['timestamp'])
    
    if events:
        event_descriptions = []
        for event in events[:5]:  # Limit to first 5 events
            event_descriptions.append(f"{event['timestamp']}: {event['description']}")
            answer_data['timestamps'].append({
                'timestamp': event['timestamp'],
                'description': event['description'],
                'relevance': 0.8
            })
        
        answer_data['answer'] = f"Key timestamps in the video: {'; '.join(event_descriptions)}"
        answer_data['confidence'] = 0.8
    else:
        answer_data['answer'] = "No timestamped events found in the analysis."
    
    return answer_data


def process_summary_question(question: str, custom_output: Dict, standard_output: Dict) -> Dict[str, Any]:
    """Process questions asking for summaries or overviews."""
    answer_data = {
        'answer': '',
        'confidence': 0.9,
        'timestamps': [],
        'players': [],
        'sources': ['custom_analysis', 'standard_analysis']
    }
    
    summary_parts = []
    
    # Game context from custom output
    if 'game_context' in custom_output:
        context = custom_output['game_context']
        teams = context.get('teams', [])
        venue = context.get('venue', '')
        if teams and venue:
            summary_parts.append(f"Game between {' vs '.join(teams)} at {venue}")
    
    # Key player actions
    if 'player_actions' in custom_output:
        actions = custom_output['player_actions'][:3]  # Top 3 actions
        for action in actions:
            player = action.get('player', '')
            action_type = action.get('action', '')
            timestamp = action.get('timestamp', '')
            summary_parts.append(f"{player} {action_type} at {timestamp}")
            answer_data['players'].append(player)
            answer_data['timestamps'].append({
                'timestamp': timestamp,
                'description': f"{player} {action_type}",
                'relevance': 0.9
            })
    
    # Standard summary
    if 'summary' in standard_output:
        summary_parts.append(standard_output['summary'])
    
    if summary_parts:
        answer_data['answer'] = '. '.join(summary_parts)
    else:
        answer_data['answer'] = "This video contains gameplay footage with various player actions and game events."
        answer_data['confidence'] = 0.5
    
    return answer_data


def process_general_question(question: str, custom_output: Dict, standard_output: Dict) -> Dict[str, Any]:
    """Process general questions by searching through all available data."""
    answer_data = {
        'answer': 'I found some information related to your question in the video analysis.',
        'confidence': 0.5,
        'timestamps': [],
        'players': [],
        'sources': ['general_search']
    }
    
    # Simple keyword matching approach
    question_keywords = set(question.lower().split())
    
    # Search through custom output
    if 'player_actions' in custom_output:
        for action in custom_output['player_actions']:
            action_text = f"{action.get('player', '')} {action.get('action', '')} {action.get('description', '')}".lower()
            if any(keyword in action_text for keyword in question_keywords):
                answer_data['players'].append(action.get('player', ''))
                answer_data['timestamps'].append({
                    'timestamp': action.get('timestamp', ''),
                    'description': f"{action.get('player', '')} {action.get('action', '')}",
                    'relevance': 0.7
                })
    
    return answer_data


def generate_comprehensive_summary(analysis_results: Dict[str, Any], summary_type: str) -> Dict[str, Any]:
    """Generate a comprehensive summary of the video."""
    custom_output = analysis_results.get('customOutput', {})
    standard_output = analysis_results.get('standardOutput', {})
    
    summary_data = {
        'title': 'Gameplay Analysis Summary',
        'summary': '',
        'key_moments': [],
        'player_stats': {},
        'game_context': {},
        'duration': 'Unknown'
    }
    
    # Generate title and context
    if 'game_context' in custom_output:
        context = custom_output['game_context']
        teams = context.get('teams', [])
        venue = context.get('venue', '')
        if teams:
            summary_data['title'] = f"{' vs '.join(teams)} Gameplay Analysis"
        summary_data['game_context'] = context
    
    # Generate summary text
    summary_parts = []
    if 'player_actions' in custom_output:
        action_count = len(custom_output['player_actions'])
        summary_parts.append(f"Analysis identified {action_count} key player actions")
        
        # Extract key moments
        for action in custom_output['player_actions'][:5]:
            summary_data['key_moments'].append({
                'timestamp': action.get('timestamp', ''),
                'event': action.get('action', ''),
                'description': f"{action.get('player', '')} {action.get('action', '')}",
                'importance': action.get('confidence', 0.8)
            })
    
    if 'chapters' in standard_output:
        chapter_count = len(standard_output['chapters'])
        summary_parts.append(f"Video contains {chapter_count} distinct chapters")
    
    summary_data['summary'] = '. '.join(summary_parts) if summary_parts else 'Video analysis completed successfully.'
    
    # Generate player stats
    if 'player_actions' in custom_output:
        player_counts = {}
        for action in custom_output['player_actions']:
            player = action.get('player', 'Unknown')
            if player not in player_counts:
                player_counts[player] = 0
            player_counts[player] += 1
        summary_data['player_stats'] = player_counts
    
    return summary_data


def search_video_content(
    analysis_results: Dict[str, Any], 
    search_query: str, 
    search_type: str, 
    time_range: Dict[str, str]
) -> Dict[str, Any]:
    """Search for specific content within the video analysis."""
    start_time = datetime.now()
    
    results = []
    search_terms = search_query.lower().split()
    
    custom_output = analysis_results.get('customOutput', {})
    standard_output = analysis_results.get('standardOutput', {})
    
    # Search player actions
    if search_type in ['players', 'all'] and 'player_actions' in custom_output:
        for action in custom_output['player_actions']:
            action_text = f"{action.get('player', '')} {action.get('action', '')} {action.get('description', '')}".lower()
            relevance = calculate_relevance(action_text, search_terms)
            
            if relevance > 0.3:  # Threshold for relevance
                results.append({
                    'timestamp': action.get('timestamp', ''),
                    'type': 'player_action',
                    'content': f"{action.get('player', '')} {action.get('action', '')}",
                    'relevanceScore': relevance,
                    'context': action.get('description', '')
                })
    
    # Search dialogue/transcript
    if search_type in ['dialogue', 'all'] and 'transcript' in standard_output:
        transcript = standard_output['transcript']
        if isinstance(transcript, list):
            for entry in transcript:
                text = entry.get('text', '').lower()
                relevance = calculate_relevance(text, search_terms)
                
                if relevance > 0.3:
                    results.append({
                        'timestamp': entry.get('timestamp', ''),
                        'type': 'dialogue',
                        'content': entry.get('text', ''),
                        'relevanceScore': relevance,
                        'context': f"Speaker: {entry.get('speaker', 'Unknown')}"
                    })
    
    # Sort results by relevance
    results.sort(key=lambda x: x['relevanceScore'], reverse=True)
    
    end_time = datetime.now()
    search_time = str(end_time - start_time)
    
    return {
        'results': results[:20],  # Limit to top 20 results
        'total': len(results),
        'search_time': search_time
    }


def calculate_relevance(text: str, search_terms: List[str]) -> float:
    """Calculate relevance score between text and search terms."""
    if not text or not search_terms:
        return 0.0
    
    text_words = set(text.lower().split())
    search_words = set(search_terms)
    
    # Calculate intersection
    common_words = text_words.intersection(search_words)
    
    if not common_words:
        return 0.0
    
    # Simple relevance calculation
    relevance = len(common_words) / len(search_words)
    
    # Boost relevance for exact phrase matches
    if ' '.join(search_terms) in text:
        relevance += 0.3
    
    return min(relevance, 1.0)


def summarize_answer(answer: str) -> str:
    """Create a brief summary of a detailed answer."""
    sentences = answer.split('.')
    if len(sentences) <= 2:
        return answer
    
    # Return first two sentences
    return '. '.join(sentences[:2]) + '.'


def format_answer_with_timestamps(answer_data: Dict[str, Any]) -> str:
    """Format answer to emphasize timestamps."""
    base_answer = answer_data['answer']
    timestamps = answer_data['timestamps']
    
    if not timestamps:
        return base_answer
    
    timestamp_info = []
    for ts in timestamps[:3]:  # Limit to 3 timestamps
        timestamp_info.append(f"{ts['timestamp']}: {ts['description']}")
    
    return f"{base_answer}\n\nKey timestamps: {'; '.join(timestamp_info)}"


def get_analysis_from_db(video_id: str) -> Dict[str, Any]:
    """Retrieve analysis results from S3."""
    try:
        # Get analysis results directly from S3
        return get_analysis_from_s3_direct(video_id)
        
    except Exception as e:
        logger.error(f"Error retrieving analysis from S3: {str(e)}")
        return {}


def get_analysis_from_s3_direct(video_id: str) -> Dict[str, Any]:
    """Directly retrieve analysis results from S3 using video ID."""
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('AWS_BUCKET_NAME')
        
        # Validate bucket name
        if not bucket_name:
            error_msg = "AWS_BUCKET_NAME environment variable is not set in Lambda configuration"
            logger.error(error_msg)
            logger.error("Please add AWS_BUCKET_NAME to Lambda environment variables")
            logger.error("Example: AWS_BUCKET_NAME=gameplay-analysis-videos-1760846170")
            raise ValueError(error_msg)
        
        logger.info(f"Using S3 bucket: {bucket_name}")
        
        # PRIMARY PATH - where api_server.py stores the combined results
        # This matches the path used in api_server.py: f'analysis/{video_id}/results.json'
        primary_path = f'analysis/{video_id}/results.json'
        
        try:
            logger.info(f"Attempting to retrieve analysis from primary path: {primary_path}")
            response = s3_client.get_object(Bucket=bucket_name, Key=primary_path)
            content = response['Body'].read().decode('utf-8')
            analysis_data = json.loads(content)
            
            logger.info(f"Successfully retrieved analysis from {primary_path}")
            return analysis_data
            
        except s3_client.exceptions.NoSuchKey:
            logger.warning(f"Analysis not found at primary path: {primary_path}")
            
            # FALLBACK - try legacy/alternative paths for backward compatibility
            fallback_paths = [
                f"analysis-results/{video_id}/results.json",
                f"data-automation-results/{video_id}/results.json",
                f"results/{video_id}/results.json"
            ]
            
            for path in fallback_paths:
                try:
                    logger.info(f"Trying fallback path: {path}")
                    response = s3_client.get_object(Bucket=bucket_name, Key=path)
                    content = response['Body'].read().decode('utf-8')
                    analysis_data = json.loads(content)
                    logger.info(f"Found analysis at fallback path: {path}")
                    return analysis_data
                except s3_client.exceptions.NoSuchKey:
                    continue
                except Exception as e:
                    logger.warning(f"Error reading {path}: {str(e)}")
                    continue
            
            logger.error(f"Analysis not found for video {video_id} in any known location")
            logger.error(f"Searched paths: {primary_path}, {', '.join(fallback_paths)}")
            return {}
        
    except Exception as e:
        logger.error(f"Error retrieving analysis from S3: {str(e)}")
        return {}


def get_analysis_results_from_s3(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve analysis results from S3 using metadata."""
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('AWS_BUCKET_NAME')
        
        analysis_data = {}
        
        # Get S3 paths from metadata
        output_s3_prefix = metadata.get('outputS3Prefix', f"analysis-results/{metadata.get('videoId')}/")
        
        # Try to get custom output
        try:
            custom_key = f"{output_s3_prefix}custom_output.json"
            response = s3_client.get_object(Bucket=bucket_name, Key=custom_key)
            content = response['Body'].read().decode('utf-8')
            analysis_data['customOutput'] = json.loads(content)
        except Exception as e:
            logger.warning(f"Could not retrieve custom output: {str(e)}")
        
        # Try to get standard output
        try:
            standard_key = f"{output_s3_prefix}standard_output.json"
            response = s3_client.get_object(Bucket=bucket_name, Key=standard_key)
            content = response['Body'].read().decode('utf-8')
            analysis_data['standardOutput'] = json.loads(content)
        except Exception as e:
            logger.warning(f"Could not retrieve standard output: {str(e)}")
        
        return analysis_data
        
    except Exception as e:
        logger.error(f"Error retrieving analysis results from S3: {str(e)}")
        return {}


def create_success_response(body: Dict[str, Any], api_path: str = '', http_method: str = '') -> Dict[str, Any]:
    """Create a successful response for Bedrock Agent."""
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': 'QueryInterface',
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
    """Create an error response for Bedrock Agent."""
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': 'QueryInterface',
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
