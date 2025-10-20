# Bedrock Data Automation Blueprint Creation Guide

This guide shows you how to create a custom hockey analysis blueprint in AWS Bedrock Data Automation using your existing custom output data.

## Step 1: Access Bedrock Data Automation

1. Go to AWS Console → Amazon Bedrock → Data Automation
2. Click "Create project"
3. Enter project name: `hockey-game-analysis`

## Step 2: Create Blueprint Using Custom Output

### Option A: Upload Sample Video + Use Blueprint Prompt (RECOMMENDED)

1. **Select/Upload file**: Choose "Upload from Computer"
2. **Upload your hockey video** (use the same video that generated your custom_output.json)
3. **Blueprint prompt**: Use this EXACT prompt based on your S3 data structure:

```
Create a hockey game analysis blueprint that extracts structured data matching this EXACT format from hockey videos:

REQUIRED OUTPUT STRUCTURE (must match exactly):
{
  "matched_blueprint": {
    "arn": "arn:aws:bedrock:us-west-2:account:blueprint/id",
    "name": "hockey_game_analysis",
    "confidence": 1
  },
  "split_video": {
    "chapter_indices": [0, 1, 2, 3]
  },
  "inference_result": {
    "game_location": "Rogers Place in Edmonton",
    "game_atmosphere": "Electric and tense atmosphere with passionate crowd support",
    "advertisements": {
      "advertiser_name": "Scotiabank, Enterprise, Castrol",
      "description": "Multiple corporate sponsors visible in the arena"
    }
  },
  "chapters": [
    {
      "inference_result": {
        "player_actions": {
          "player_name": "Sam Reinhart",
          "action_type": "goal",
          "description": "Sam Reinhart scores a goal for the Panthers"
        },
        "spectator_reactions": {
          "reaction_type": "cheering",
          "description": "The spectators display intense and passionate reactions"
        },
        "game_events": {
          "event_type": "goal",
          "description": "The Panthers score two goals in the first period"
        },
        "locker_room_scenes": {
          "scene_type": "coach_speech",
          "description": "Kris Knoblauch addressing his team with motivational speech"
        },
        "team_bus_scenes": {
          "scene_type": "exiting",
          "description": "A white TRAXX bus with players exiting into facility"
        }
      },
      "frames": [],
      "chapter_index": 0,
      "start_timecode_smpte": "00:00:00;00",
      "end_timecode_smpte": "00:00:13;27",
      "start_timestamp_millis": 0,
      "end_timestamp_millis": 13881,
      "start_frame_index": 0,
      "end_frame_index": 416,
      "duration_smpte": "00:00:13;27",
      "duration_millis": 13881,
      "duration_frames": 417
    }
  ]
}

CRITICAL REQUIREMENTS:
- EXACT field names: player_actions, spectator_reactions, game_events, locker_room_scenes, team_bus_scenes
- Include empty "frames": [] array in each chapter
- Use precise SMPTE timecode format: "HH:MM:SS;FF"
- Calculate duration_millis, duration_frames from start/end times
- Action types: goal, assist, save, hit, pass, shot, penalty, faceoff, fight
- Reaction types: cheering, booing, sitting, standing, waving
- Event types: goal, penalty, fight, timeout, period_end, celebration
- Scene types: preparation, coach_speech, celebration, interview, arrival, departure, exiting, boarding
- Detect specific player names (e.g., Sam Reinhart, Connor McDavid)
- Identify venue details and corporate sponsors
- Handle "Not applicable" or empty strings for missing data
- Segment video into 3-4 meaningful chapters based on scene changes

Focus on NHL hockey analysis with precise timestamps and comprehensive scene detection.
```

4. Click **"Generate blueprint"**
5. Wait for blueprint generation (1-2 minutes)
6. Review and refine the generated blueprint
7. Click **"Save blueprint"**

### Option B: Manual Blueprint Creation

1. Click **"Manually create new blueprint"**
2. Upload the JSON file: `backend/bedrock-data-automation/hockey-blueprint.json`
3. Configure the blueprint settings:
   - **Input types**: Video (MP4, MOV), Audio (MP3, WAV)
   - **Output format**: JSON
   - **Analysis types**: Multi-modal (video + audio + text)

## Step 3: Configure Project Settings

1. **Output Configuration**:
   - **S3 Bucket**: Select your gameplay analysis bucket
   - **Output Prefix**: `analysis-results/`
   - **Format**: JSON

2. **Encryption**: 
   - Use default AWS managed keys

3. **Tags** (optional):
   - `Project`: `hockey-analysis`
   - `Environment`: `production`

## Step 4: Test the Blueprint

1. **Upload test video**: Use a short hockey clip
2. **Run analysis**: Start a test job
3. **Review output**: Check if the output matches your expected format
4. **Refine blueprint**: Adjust if needed

## Step 5: Get Project ARN

1. After project creation, copy the **Project ARN**
2. Update your `backend/.env` file:
   ```bash
   DATA_AUTOMATION_PROJECT_ARN=arn:aws:bedrock:region:account:data-automation-project/project-id
   ```

## Expected Output Structure

Your blueprint should generate output matching this structure:

```json
{
  "matched_blueprint": {
    "arn": "arn:aws:bedrock:us-east-1:account:blueprint/hockey-game-analysis",
    "name": "hockey_game_analysis",
    "confidence": 1.0
  },
  "inference_result": {
    "game_location": "Rogers Place in Edmonton",
    "game_atmosphere": "Electric atmosphere with passionate crowd support",
    "advertisements": {
      "advertiser_name": "Scotiabank, Enterprise, Castrol",
      "description": "Multiple corporate sponsors visible throughout the arena"
    }
  },
  "chapters": [
    {
      "inference_result": {
        "player_actions": {
          "player_name": "Sam Reinhart",
          "action_type": "goal",
          "description": "Sam Reinhart scores for the Panthers"
        },
        "spectator_reactions": {
          "reaction_type": "cheering", 
          "description": "Crowd erupts in celebration"
        },
        "game_events": {
          "event_type": "goal",
          "description": "First period goal changes momentum"
        }
      },
      "start_timecode_smpte": "00:00:26;03",
      "end_timecode_smpte": "00:05:00:00",
      "start_timestamp_millis": 26093,
      "end_timestamp_millis": 299999,
      "duration_frames": 8322
    }
  ]
}
```

## Troubleshooting

### Blueprint Generation Issues
- **Prompt too long**: Reduce prompt to under 1000 words
- **Output format not recognized**: Provide clearer JSON structure examples
- **Missing fields**: Add specific field requirements to prompt

### Analysis Quality Issues
- **Poor player detection**: Add more specific player action examples
- **Incorrect timestamps**: Verify SMPTE format requirements
- **Missing game events**: Enhance event detection criteria

### Integration Issues
- **Lambda function errors**: Verify PROJECT_ARN is correct
- **S3 permissions**: Ensure Bedrock can write to output bucket
- **API calls failing**: Check IAM permissions for Bedrock Data Automation

## Next Steps

1. Create the blueprint using the guide above
2. Test with sample hockey video
3. Update `DATA_AUTOMATION_PROJECT_ARN` in backend/.env
4. Run `./deploy.sh deploy-lambda` to update Lambda functions
5. Test end-to-end video analysis through your application
