# External References & Model Sources

This document lists all external models, libraries, and data sources used in the Robotic Arm Feedback System.

---

## Face Pain Detection Module

### 1. OpenCV DNN Face Detector

**Purpose:** Detect faces in video frames

**Model Files:**
| File | Source | Size |
|------|--------|------|
| `deploy.prototxt` | OpenCV GitHub | ~28 KB |
| `res10_300x300_ssd_iter_140000.caffemodel` | OpenCV 3rdparty | ~10 MB |

**URLs:**
- Prototxt: https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt
- Caffe Model: https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel

**Architecture:** Single Shot Detector (SSD) with ResNet-10 backbone

**License:** BSD-3-Clause (OpenCV License)

**Reference:**
- OpenCV DNN Module: https://docs.opencv.org/master/d2/d58/tutorial_table_of_content_dnn.html

---

### 2. LBF Facial Landmark Detector

**Purpose:** Detect 68 facial landmarks for expression analysis

**Model File:**
| File | Source | Size |
|------|--------|------|
| `lbfmodel.yaml` | GSOC 2017 Project | ~54 MB |

**URL:**
- https://raw.githubusercontent.com/kurnianggoro/GSOC2017/master/data/lbfmodel.yaml

**Architecture:** Local Binary Features (LBF) cascade regression

**Landmarks:** 68-point facial landmark model
- Points 0-16: Jaw contour
- Points 17-21: Right eyebrow
- Points 22-26: Left eyebrow
- Points 27-35: Nose
- Points 36-41: Right eye
- Points 42-47: Left eye
- Points 48-59: Outer lip
- Points 60-67: Inner lip

**License:** BSD-3-Clause

**Reference:**
- Paper: "One Millisecond Face Alignment with an Ensemble of Regression Trees" (Kazemi & Sullivan, 2014)
- GSOC Project: https://github.com/kurnianggoro/GSOC2017

---

### 3. Haar Cascade (Fallback)

**Purpose:** Fallback face detection when DNN models unavailable

**Model File:**
| File | Source |
|------|--------|
| `haarcascade_frontalface_default.xml` | OpenCV (bundled) |

**Location:** Included with OpenCV installation (`cv2.data.haarcascades`)

**License:** BSD-3-Clause (OpenCV License)

**Reference:**
- Original Paper: "Rapid Object Detection using a Boosted Cascade of Simple Features" (Viola & Jones, 2001)

---

## YouTube Video Support

### yt-dlp Library

**Purpose:** Extract video stream URLs from YouTube

**Package:** `yt-dlp`

**PyPI:** https://pypi.org/project/yt-dlp/

**GitHub:** https://github.com/yt-dlp/yt-dlp

**License:** Unlicense

**Usage:** Extracts direct video stream URLs for OpenCV to process

---

## Python Dependencies

### Core Libraries

| Package | Purpose | License |
|---------|---------|---------|
| `opencv-python` | Computer vision, video processing | Apache 2.0 |
| `opencv-contrib-python` | Additional OpenCV modules (face) | Apache 2.0 |
| `numpy` | Numerical computations | BSD-3-Clause |
| `flask` | Web dashboard server | BSD-3-Clause |
| `pyserial` | Arduino serial communication | BSD-3-Clause |
| `yt-dlp` | YouTube video extraction | Unlicense |

---

## Pain Detection Theory

### Facial Action Coding System (FACS)

The pain detection algorithm is based on research into facial expressions associated with pain:

**Key Action Units (AUs) for Pain:**

| AU | Name | Description |
|----|------|-------------|
| AU4 | Brow Lowerer | Furrowed/lowered eyebrows |
| AU6 | Cheek Raiser | Raised cheeks, crow's feet |
| AU7 | Lid Tightener | Narrowed eye aperture |
| AU9 | Nose Wrinkler | Wrinkled nose bridge |
| AU10 | Upper Lip Raiser | Raised upper lip |
| AU43 | Eyes Closed | Closed eyes |

**References:**
1. Ekman, P., & Friesen, W. V. (1978). *Facial Action Coding System: A Technique for the Measurement of Facial Movement*. Consulting Psychologists Press.

2. Prkachin, K. M. (1992). "The consistency of facial expressions of pain: a comparison across modalities." *Pain*, 51(3), 297-306.

3. Prkachin, K. M., & Solomon, P. E. (2008). "The structure, reliability and validity of pain expression: Evidence from patients with shoulder pain." *Pain*, 139(2), 267-274.

**Prkachin Pain Intensity Scale:**
```
Pain = AU4 + max(AU6, AU7) + max(AU9, AU10) + AU43
```

---

## Model Storage Location

Models are automatically downloaded and stored in:
```
face_detection/models/
├── deploy.prototxt           # Face detector architecture
├── face_model.caffemodel     # Face detector weights
└── lbfmodel.yaml             # Facial landmark model
```

---

## Data Sources

### Sample Sensor Data

The sample CSV files in `data/` are **synthetically generated** for testing purposes and do not contain real sensor readings.

| File | Rows | Description |
|------|------|-------------|
| `sample_sensor_data.csv` | 113 | Full pressure cycle simulation |
| `test_small.csv` | 15 | Quick test dataset |

---

## Acknowledgments

- **OpenCV Team** - For the DNN face detector and computer vision tools
- **Kurnianggoro** - For the LBF facial landmark model (GSOC 2017)
- **yt-dlp Contributors** - For YouTube video extraction
- **FACS Researchers** - For facial expression coding methodology

---

## License Compliance

All external models and libraries used in this project are under permissive open-source licenses (BSD, Apache 2.0, Unlicense) that allow for free use, modification, and distribution.

For commercial use, please verify license terms for each component.

