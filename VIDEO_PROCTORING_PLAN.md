# Video Proctoring Implementation Plan

## Information Gathered

1. **Project Structure**: Academic Integrity System with FastAPI backend and React frontend
2. **Existing Proctoring Module**: Behavioral analysis (paste events, tab switches, focus lost, typing speed, idle periods)
3. **Module Pattern**: All modules extend `BaseModule` and implement `analyze(text, metadata)` returning `ModuleResult`
4. **API Pattern**: File uploads via `/api/v1/submissions` with session data passed as JSON
5. **Database**: SQLAlchemy models in `db/models.py`
6. **Frontend**: React with components for upload and results

## Plan: Video Proctoring Implementation

### Phase 1: Backend Updates

#### 1.1 Update `db/models.py`
- Add `VideoProctoringRecord` model for storing video session data
- Fields: id, submission_id, face_detected, multiple_faces, no_face_count, low_light_count, device_change_count, created_at

#### 1.2 Update `modules/proctoring/detector.py`
- Extend `ProctoringModule` to accept video proctoring metadata
- Add video-specific analysis methods:
  - Face detection analysis
  - Multiple faces detection
  - No face / away from camera detection
  - Low light conditions detection
  - Device/camera change detection
- Add video event flags and scoring

#### 1.3 Create `api/v1/video_proctoring.py`
- New API endpoints:
  - `POST /video-proctoring/session` - Start video session
  - `POST /video-proctoring/session/{session_id}/event` - Report video events (face_detected, face_lost, multiple_faces, etc.)
  - `GET /video-proctoring/session/{session_id}` - Get session status
  - `DELETE /video-proctoring/session/{session_id}` - End session

#### 1.4 Update `api/v1/submissions.py`
- Integrate video proctoring data into submission metadata

### Phase 2: Frontend Updates

#### 2.1 Create `frontend/src/components/Proctoring/VideoRecorder.jsx`
- WebRTC video capture component
- Real-time face detection using browser APIs or lightweight library
- Recording status indicators
- Camera/mic controls

#### 2.2 Create `frontend/src/components/Proctoring/VideoEvents.jsx`
- Component to send video events to backend
- Handle face detection, multiple faces, no face events

#### 2.3 Update `frontend/src/components/Upload/SubmissionForm.jsx`
- Add video proctoring toggle
- Integrate VideoRecorder component
- Show video proctoring results in ModuleResultCard

#### 2.4 Update `frontend/src/api/index.js`
- Add API methods for video proctoring endpoints

### Phase 3: Configuration

#### 3.1 Update `core/config.py`
- Add video proctoring settings:
  - `VIDEO_PROCTORING_ENABLED`: bool = True
  - `VIDEO_PROCTORING_REQUIRED`: bool = False
  - `VIDEO_MAX_DURATION_MINUTES`: int = 120

### Dependent Files to be Edited

1. `db/models.py` - Add VideoProctoringRecord model
2. `modules/proctoring/detector.py` - Extend with video analysis
3. `api/v1/video_proctoring.py` - New API endpoints (create new file)
4. `api/main.py` - Register new router
5. `api/v1/submissions.py` - Integrate video data
6. `frontend/src/components/Proctoring/VideoRecorder.jsx` - New component
7. `frontend/src/components/Proctoring/VideoEvents.jsx` - New component
8. `frontend/src/components/Upload/SubmissionForm.jsx` - Add video toggle
9. `frontend/src/api/index.js` - Add video API methods

### Followup Steps

1. Test WebRTC video capture in development
2. Test video event API endpoints
3. Test integration with submission flow
4. Verify video proctoring results display correctly

