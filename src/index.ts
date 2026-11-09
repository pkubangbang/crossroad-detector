/**
 * index.ts — public entry point for @pkubangbang/crossroad-detector.
 *
 * Exports:
 *   - CrossroadDetector + TurningWordMatch — the detector SDK.
 *   - CrossroadUnavailableError — thrown when detection could NOT run.
 *   - createSegmenter / segmentsOf — where a cut may land: contiguous,
 *     non-overlapping segments with a `cutKind`. The model's own segment set
 *     (`buildSpans`) is NOT exported: it overlaps by design, so it is not a
 *     set of cut positions, and only the server needs it.
 */

export {
  CrossroadDetector,
  CrossroadUnavailableError,
  type CrossroadDetectorOptions,
  type CrossroadUnavailableReason,
  type TurningWordMatch,
} from './client.js';

export {
  createSegmenter,
  segmentsOf,
  type Segment,
  type SegmentCutKind,
  type Segmenter,
  type SegmenterOptions,
} from './segmenter.js';
