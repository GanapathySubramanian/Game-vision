"""
Simplified FastAPI server for Bedrock Agent Gameplay Analysis.
All endpoints consolidated in one file for clarity.
No DynamoDB dependency - uses in-memory storage and S3.
"""

import os
import json
import uuid
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import boto3
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import shared helpers
from shared.aws_helpers import (
    generate_presigned_upload_url,
    get_bedrock_agent_runtime_client,
    invoke_data_automation_and_get_results,
    get_s3_client,
    get_bucket_name
)

# Initialize FastAPI app
app = FastAPI(
    title="Gameplay Analysis API",
    description="Simplified API server for Bedrock Agent gameplay analysis",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://*.amplifyapp.com",  # Allow all Amplify subdomains
        "*"  # Allow all origins for now (restrict in production)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
BEDROCK_AGENT_ID = os.environ.get('BEDROCK_AGENT_ID')
BEDROCK_AGENT_ALIAS_ID = os.environ.get('BEDROCK_AGENT_ALIAS_ID', 'TSTALIASID')

# In-memory storage (replaces DynamoDB for local dev)
video_metadata: Dict[str, Dict[str, Any]] = {}
active_sessions: Dict[str, Dict[str, Any]] = {}

# Pydantic models
class VideoUploadRequest(BaseModel):
    fileName: str
    contentType: str = "video/mp4"

class VideoUploadResponse(BaseModel):
    uploadUrl: str
    s3Uri: str
    videoId: str

class AnalyzeVideoRequest(BaseModel):
    videoId: str
    s3Uri: str

class StartConversationRequest(BaseModel):
    videoId: Optional[str] = None

class SendMessageRequest(BaseModel):
    sessionId: str
    message: str
    videoId: Optional[str] = None

# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Gameplay Analysis API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "services": {
            "bedrock_agent": bool(BEDROCK_AGENT_ID),
            "aws_credentials": True,
            "storage": "in-memory + S3"
        },
        "videos_tracked": len(video_metadata),
        "active_sessions": len(active_sessions)
    }

# ============================================================================
# VIDEO MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/api/video/upload-url", response_model=VideoUploadResponse)
async def get_video_upload_url(request: VideoUploadRequest):
    """Generate presigned URL for video upload."""
    try:
        upload_info = await generate_presigned_upload_url(
            request.fileName, 
            request.contentType
        )
        
        video_id = str(uuid.uuid4())
        
        # Store metadata in memory
        video_metadata[video_id] = {
            'videoId': video_id,
            'fileName': request.fileName,
            'contentType': request.contentType,
            's3Uri': upload_info['s3_uri'],
            's3Key': upload_info['key'],
            'status': 'uploaded',
            'analysisStatus': 'pending',
            'uploadTime': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Generated upload URL for video {video_id}")
        
        return VideoUploadResponse(
            uploadUrl=upload_info['upload_url'],
            s3Uri=upload_info['s3_uri'],
            videoId=video_id
        )
    except Exception as e:
        logger.error(f"Failed to generate upload URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# VIDEO ANALYSIS ENDPOINTS
# ============================================================================

@app.post("/api/video/analyze/{video_id}")
async def analyze_video(video_id: str):
    """Trigger video analysis using Bedrock Data Automation and wait for results."""
    try:
        if video_id not in video_metadata:
            raise HTTPException(status_code=404, detail="Video not found")
        
        metadata = video_metadata[video_id]
        s3_uri = metadata.get('s3Uri')
        
        if not s3_uri:
            raise HTTPException(status_code=400, detail="Video S3 URI not found")
        
        # Update status
        video_metadata[video_id]['analysisStatus'] = 'in-progress'
        video_metadata[video_id]['analysisStartedAt'] = datetime.utcnow().isoformat()
        
        logger.info(f"Starting synchronous analysis for video {video_id}")
        
        # Process video analysis synchronously (wait for results)
        start_time = datetime.utcnow()
        
        try:
            bda_results = await invoke_data_automation_and_get_results(s3_uri)
            
            # Write raw BDA results to file for debugging/inspection
            # bda_raw_file = f'bda_raw_results/{video_id}_raw_bda_output.json'
            # os.makedirs('bda_raw_results', exist_ok=True)
            # with open(bda_raw_file, 'w') as f:
            #     json.dump(bda_results, f, indent=2)
            # logger.info(f"Wrote raw BDA results to {bda_raw_file}")
            
            end_time = datetime.utcnow()
            processing_duration = (end_time - start_time).total_seconds()
            
            # Process the results (aws_helpers already processes them)
            results = bda_results["customOutput"]
            
            if results:
                # Write processed results to file for debugging/inspection
                processed_file = f'bda_raw_results/{video_id}_processed_results.json'
                # with open(processed_file, 'w') as f:
                #     json.dump(results, f, indent=2)
                # logger.info(f"Wrote processed results to {processed_file}")
                
                # Store results in S3
                s3_client = get_s3_client()
                bucket_name = get_bucket_name()
                
                analysis_key = f'analysis/{video_id}/results.json'
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=analysis_key,
                    Body=json.dumps(results, indent=2),
                    ContentType='application/json'
                )
                
                # Update metadata
                video_metadata[video_id].update({
                    'analysisStatus': 'completed',
                    'analysisCompletedAt': end_time.isoformat(),
                    'processingDuration': processing_duration
                })
                
                logger.info(f"Completed analysis for video {video_id} in {processing_duration:.2f}s")
                
                return {
                    "videoId": video_id,
                    "status": "completed",
                    "results": results,
                    "metadata": {
                        "analysisTime": end_time.isoformat(),
                        "processingDuration": processing_duration,
                        "videoFileName": metadata.get('fileName')
                    },
                    "message": f"Analysis completed in {processing_duration:.1f} seconds"
                }
            else:
                video_metadata[video_id].update({
                    'analysisStatus': 'failed',
                    'analysisCompletedAt': end_time.isoformat(),
                    'errorMessage': 'Analysis returned no results'
                })
                raise HTTPException(status_code=500, detail="Analysis returned no results")
                
        except Exception as analysis_error:
            logger.error(f"Analysis failed for video {video_id}: {analysis_error}")
            video_metadata[video_id].update({
                'analysisStatus': 'failed',
                'analysisCompletedAt': datetime.utcnow().isoformat(),
                'errorMessage': str(analysis_error)
            })
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(analysis_error)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# COMPATIBILITY ENDPOINTS (for old frontend)
# ============================================================================

@app.post("/api/analyze-video/{video_id}")
async def analyze_video_compat(video_id: str):
    """Compatibility endpoint for old frontend URL."""
    return await analyze_video(video_id)

# ============================================================================
# BEDROCK AGENT ENDPOINTS
# ============================================================================

@app.post("/api/agent/conversation/start")
async def start_conversation(request: StartConversationRequest):
    """Start a new conversation with the Bedrock Agent."""
    try:
        session_id = str(uuid.uuid4())
        
        # Get S3 URI from video metadata if videoId is provided
        s3_uri = None
        if request.videoId and request.videoId in video_metadata:
            s3_uri = video_metadata[request.videoId].get('s3Uri')
        
        active_sessions[session_id] = {
            "sessionId": session_id,
            "videoId": request.videoId,
            "s3Uri": s3_uri,
            "createdAt": datetime.utcnow().isoformat(),
            "messages": []
        }
        
        logger.info(f"Started conversation session: {session_id} with video: {request.videoId}")
        
        return {"sessionId": session_id}
        
    except Exception as e:
        logger.error(f"Failed to start conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agent/conversation/message")
async def send_message(request: SendMessageRequest):
    """Send a message to the Bedrock Agent with session attributes."""
    try:
        if request.sessionId not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if not BEDROCK_AGENT_ID:
            raise HTTPException(status_code=500, detail="Bedrock Agent ID not configured")
        
        session = active_sessions[request.sessionId]
        bedrock_agent_runtime = get_bedrock_agent_runtime_client()
        
        # Prepare session attributes with S3 URI
        session_state = {}
        if session.get('s3Uri'):
            session_state = {
                'sessionAttributes': {
                    'videoS3Uri': session['s3Uri'],
                    'videoId': session.get('videoId', '')
                }
            }
            logger.info(f"Sending message with session attributes: {session_state}")
        
        # Invoke agent with session attributes
        invoke_params = {
            'agentId': BEDROCK_AGENT_ID,
            'agentAliasId': BEDROCK_AGENT_ALIAS_ID,
            'sessionId': request.sessionId,
            'inputText': request.message,
            'enableTrace': True,
            'endSession': False
        }
        
        # Add session state if available
        if session_state:
            invoke_params['sessionState'] = session_state
        
        response = bedrock_agent_runtime.invoke_agent(**invoke_params)
        
        # Process streaming response
        output_text = ""
        if 'completion' in response:
            for event in response['completion']:
                if 'chunk' in event:
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        output_text += chunk['bytes'].decode('utf-8')
        
        # Store message in session
        session['messages'].extend([
            {
                "role": "user",
                "content": request.message,
                "timestamp": datetime.utcnow().isoformat()
            },
            {
                "role": "assistant", 
                "content": output_text,
                "timestamp": datetime.utcnow().isoformat()
            }
        ])
        
        return {
            "sessionId": request.sessionId,
            "output": {"text": output_text}
        }
        
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agent/conversation/end")
async def end_conversation(request: dict):
    """End a conversation session."""
    session_id = request.get('sessionId')
    
    if session_id in active_sessions:
        del active_sessions[session_id]
        logger.info(f"Ended conversation session: {session_id}")
    
    return {"message": "Conversation ended"}

# ============================================================================
# QUERY ENDPOINTS
# ============================================================================

@app.post("/api/query/ask")
async def ask_question(request: dict):
    """Ask a question about video content."""
    try:
        video_id = request.get('videoId')
        question = request.get('question')
        
        if not video_id or not question:
            raise HTTPException(status_code=400, detail="videoId and question are required")
        
        if video_id not in video_metadata:
            raise HTTPException(status_code=404, detail="Video not found")
        
        metadata = video_metadata[video_id]
        
        if metadata.get('analysisStatus') != 'completed':
            raise HTTPException(status_code=400, detail="Video analysis not completed yet")
        
        # Get analysis results from S3
        s3_client = get_s3_client()
        bucket_name = get_bucket_name()
        
        try:
            analysis_key = f'analysis/{video_id}/results.json'
            response = s3_client.get_object(Bucket=bucket_name, Key=analysis_key)
            analysis_data = json.loads(response['Body'].read().decode('utf-8'))
            
            # Use Bedrock Agent with structured context
            from shared.aws_helpers import invoke_agent_with_structured_context
            
            structured_data = {
                'game_events': analysis_data.get('customOutput', {}).get('game_events', []),
                'player_actions': analysis_data.get('customOutput', {}).get('player_actions', []),
                'game_context': analysis_data.get('customOutput', {}).get('game_context', {}),
                'metadata': analysis_data.get('standardOutput', {}).get('metadata', {})
            }
            
            answer_data = await invoke_agent_with_structured_context(
                question=question,
                structured_data=structured_data,
                session_id=request.get('sessionId', str(uuid.uuid4()))
            )
            
            return {
                "videoId": video_id,
                "question": question,
                "answer": answer_data['answer'],
                "confidence": answer_data['confidence'],
                "relevantTimestamps": answer_data['relevant_timestamps'],
                "relatedPlayers": answer_data['related_players']
            }
            
        except s3_client.exceptions.NoSuchKey:
            raise HTTPException(status_code=404, detail="Analysis results not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to answer question: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def process_video_analysis(video_id: str, s3_uri: str):
    """Background task to process video analysis."""
    try:
        logger.info(f"Starting analysis for video {video_id}")
        
        start_time = datetime.utcnow()
        results = await invoke_data_automation_and_get_results(s3_uri)
        end_time = datetime.utcnow()
        
        processing_duration = (end_time - start_time).total_seconds()
        
        if results:
            # Store results in S3
            s3_client = get_s3_client()
            bucket_name = get_bucket_name()
            
            analysis_key = f'analysis/{video_id}/results.json'
            s3_client.put_object(
                Bucket=bucket_name,
                Key=analysis_key,
                Body=json.dumps(results, indent=2),
                ContentType='application/json'
            )
            
            # Update metadata
            video_metadata[video_id].update({
                'analysisStatus': 'completed',
                'analysisCompletedAt': end_time.isoformat(),
                'processingDuration': processing_duration
            })
            
            logger.info(f"Completed analysis for video {video_id} in {processing_duration:.2f}s")
        else:
            video_metadata[video_id].update({
                'analysisStatus': 'failed',
                'analysisCompletedAt': end_time.isoformat(),
                'errorMessage': 'Analysis returned no results'
            })
            logger.error(f"Analysis failed for video {video_id}: No results")
        
    except Exception as e:
        logger.error(f"Failed to process video analysis: {e}")
        video_metadata[video_id].update({
            'analysisStatus': 'failed',
            'analysisCompletedAt': datetime.utcnow().isoformat(),
            'errorMessage': str(e)
        })

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Gameplay Analysis API Server")
    
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
