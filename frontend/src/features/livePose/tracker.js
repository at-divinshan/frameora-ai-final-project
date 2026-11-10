// Deferred: restore @mediapipe/tasks-vision 0.10.32 and /public/mediapipe assets before reactivation.
import { DETECTION_LIMIT } from './groupTracking';
import { FilesetResolver, PoseLandmarker } from '@mediapipe/tasks-vision';
// Version-pinned assets; only model/WASM downloads leave the device, never frames.
export async function createTracker() {
  const vision=await FilesetResolver.forVisionTasks('/mediapipe/wasm');
  return PoseLandmarker.createFromOptions(vision, {
    baseOptions:{modelAssetPath:'/mediapipe/pose_landmarker_lite.task',delegate:'CPU'},
    outputSegmentationMasks:true,
    runningMode:'VIDEO',numPoses:DETECTION_LIMIT,minPoseDetectionConfidence:.6,
    minPosePresenceConfidence:.6,minTrackingConfidence:.6,
  });
}
