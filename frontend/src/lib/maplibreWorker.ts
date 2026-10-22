// MapLibre 6 loads its worker from a file next to its own module, which a
// bundler moves. Let Vite bundle the worker and tell MapLibre where it is.
import { setWorkerUrl } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

setWorkerUrl(workerUrl)
