# TODO: Video Proctoring Implementation

## Step 1: Add Computer Vision Dependencies
- [ ] Add opencv-python, face_recognition, Pillow, pytesseract to requirements.txt
- [ ] Install dependencies

## Step 2: Create Video Proctoring Service
- [ ] Create services/video_processor.py
- [ ] Implement face detection
- [ ] Implement multiple face detection
- [ ] Implement liveness detection (blink, movement)
- [ ] Implement screenshot/anomaly detection

## Step 3: Create Document Scanner Service
- [ ] Create services/document_scanner.py
- [ ] Implement edge detection
- [ ] Implement perspective correction
- [ ] Implement document quality assessment

## Step 4: Update Text Extractor
- [ ] Add OCR support using pytesseract

## Step 5: Enhance Proctoring Module
- [ ] Integrate video analysis into modules/proctoring/detector.py
- [ ] Add face detection results to evidence
- [ ] Add document scanning results to evidence

## Step 6: Testing
- [ ] Test video processor
- [ ] Test document scanner
- [ ] Test proctoring module integration

