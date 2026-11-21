import { ContactShadows, Edges, Environment, Lightformer, OrbitControls } from '@react-three/drei'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import clsx from 'clsx'
import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import * as THREE from 'three'

import type { MaterialFamily, PolygonJson, Remnant, SheetAnalysis } from '../../lib/api'
import { fmtKg, fmtMm } from '../../lib/format'
import { createMaterials } from './materials'
import { visualThickness } from './thickness'

/** Scene units: the sheet's longest side is always this long. */
const SCENE_SIZE = 10
const RESTING_LABELS = 4

export type ViewMode = '3d' | 'top'

interface SheetViewerProps {
  sheet: SheetAnalysis
  family: MaterialFamily | null
  thicknessMm: number | null
  highlighted: string | null
  onHighlight: (id: string | null) => void
  mode: ViewMode
}

interface Frame {
  scale: number
  cx: number
  cy: number
  depth: number
}

type Register = (id: string, anchor: THREE.Object3D | null) => void

function toShape(poly: PolygonJson, f: Frame): THREE.Shape {
  const pt = ([x, y]: [number, number]) => new THREE.Vector2((x - f.cx) * f.scale, (y - f.cy) * f.scale)
  const shape = new THREE.Shape(poly.exterior.map(pt))
  for (const hole of poly.holes) shape.holes.push(new THREE.Path(hole.map(pt)))
  return shape
}

function extrude(polys: PolygonJson[], f: Frame, depth: number): THREE.ExtrudeGeometry | null {
  const shapes = polys.filter((p) => p.exterior.length >= 3).map((p) => toShape(p, f))
  if (!shapes.length) return null
  return new THREE.ExtrudeGeometry(shapes, { depth, bevelEnabled: false, curveSegments: 1 })
}

function RemnantBlock({
  remnant,
  frame,
  material,
  index,
  highlighted,
  onHighlight,
  register,
}: {
  remnant: Remnant
  frame: Frame
  material: THREE.MeshStandardMaterial
  index: number
  highlighted: boolean
  onHighlight: (id: string | null) => void
  register: Register
}) {
  const group = useRef<THREE.Group>(null)
  const mesh = useRef<THREE.Mesh>(null)
  // Each remnant gets its own copy so its glow can change independently.
  const [mat] = useState(() => material.clone())
  const born = useRef<number | null>(null)
  const w = remnant.width * frame.scale
  const h = remnant.height * frame.scale
  const lift = frame.depth * 2.4 + 0.08

  useFrame((state, delta) => {
    if (!group.current) return
    born.current ??= state.clock.elapsedTime
    const age = state.clock.elapsedTime - born.current - 0.35 - index * 0.12
    const target = age < 0 ? 0 : highlighted ? lift * 2 : lift
    group.current.position.y = THREE.MathUtils.damp(group.current.position.y, target, 6, delta)
    const m = mesh.current?.material as THREE.MeshStandardMaterial | undefined
    if (m) m.emissiveIntensity = THREE.MathUtils.damp(m.emissiveIntensity, highlighted ? 0.22 : 0, 8, delta)
  })

  useEffect(() => () => mat.dispose(), [mat])

  const cx = (remnant.x + remnant.width / 2 - frame.cx) * frame.scale
  const cz = -(remnant.y + remnant.height / 2 - frame.cy) * frame.scale
  const anchorRef = useCallback((obj: THREE.Object3D | null) => register(remnant.id, obj), [register, remnant.id])

  return (
    <group ref={group}>
      <mesh
        position={[cx, frame.depth / 2, cz]}
        ref={mesh}
        material={mat}
        castShadow
        receiveShadow
        onPointerOver={(e) => {
          e.stopPropagation()
          onHighlight(remnant.id)
        }}
        onPointerOut={() => onHighlight(null)}
      >
        <boxGeometry args={[w, frame.depth, h]} />
        <Edges color={highlighted ? '#ecfbc4' : '#c8f169'} threshold={15} />
      </mesh>
      <object3D ref={anchorRef} position={[cx, frame.depth, cz]} />
    </group>
  )
}

/** Position a label element on screen (or hide it) without going through React. */
function placeLabel(el: HTMLDivElement, x: number, y: number, visible: boolean) {
  el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) translate(-50%, -135%)`
  el.style.opacity = visible ? '1' : '0'
}

/** Moves the DOM labels to follow their 3D anchors, without re-rendering React. */
function LabelProjector({
  anchors,
  labels,
}: {
  anchors: RefObject<Map<string, THREE.Object3D>>
  labels: RefObject<Map<string, HTMLDivElement>>
}) {
  const v = useMemo(() => new THREE.Vector3(), [])
  useFrame(({ camera, size }) => {
    for (const [id, el] of labels.current) {
      const anchor = anchors.current.get(id)
      if (!anchor) {
        placeLabel(el, 0, 0, false)
        continue
      }
      anchor.getWorldPosition(v).project(camera)
      placeLabel(el, ((v.x + 1) / 2) * size.width, ((1 - v.y) / 2) * size.height, v.z < 1)
    }
  })
  return null
}

function CameraRig({ mode, distance }: { mode: ViewMode; distance: number }) {
  const { camera } = useThree()
  const controls = useThree((s) => s.controls) as { update: () => void } | null
  const goal = useRef<THREE.Vector3 | null>(null)

  useEffect(() => {
    goal.current =
      mode === 'top'
        ? new THREE.Vector3(0, distance * 1.3, distance * 0.12)
        : new THREE.Vector3(distance * 0.38, distance * 0.6, distance * 0.86)
  }, [mode, distance])

  useFrame((_, delta) => {
    if (!goal.current) return
    camera.position.lerp(goal.current, 1 - Math.exp(-delta * 4))
    controls?.update()
    if (camera.position.distanceTo(goal.current) < 0.01) goal.current = null
  })
  return null
}

function Sheet({
  sheet,
  family,
  thicknessMm,
  highlighted,
  onHighlight,
  register,
}: Omit<SheetViewerProps, 'mode'> & { register: Register }) {
  const frame = useMemo<Frame>(() => {
    const scale = SCENE_SIZE / Math.max(sheet.width, sheet.height)
    return {
      scale,
      cx: sheet.width / 2,
      cy: sheet.height / 2,
      depth: visualThickness(sheet, thicknessMm).shown * scale,
    }
  }, [sheet, thicknessMm])

  const materials = useMemo(() => createMaterials(family), [family])
  const geometry = sheet.geometry
  const scrap = useMemo(() => (geometry ? extrude(geometry.scrap, frame, frame.depth) : null), [geometry, frame])
  const parts = useMemo(
    () => (geometry ? extrude(geometry.parts, frame, frame.depth * 0.92) : null),
    [geometry, frame],
  )
  useEffect(
    () => () => {
      scrap?.dispose()
      parts?.dispose()
    },
    [scrap, parts],
  )

  return (
    <group>
      {/* Extruded shapes live in XY; lay them flat so the sheet's Y runs away from the viewer. */}
      <group rotation={[-Math.PI / 2, 0, 0]}>
        {scrap && <mesh geometry={scrap} material={materials.stock} castShadow receiveShadow />}
        {parts && (
          <mesh
            geometry={parts}
            material={materials.part}
            position={[0, 0, -frame.depth * 0.18]}
            castShadow
            receiveShadow
          />
        )}
      </group>
      {sheet.remnants.map((r, i) => (
        <RemnantBlock
          key={r.id}
          remnant={r}
          frame={frame}
          material={materials.remnant}
          index={i}
          highlighted={highlighted === r.id}
          onHighlight={onHighlight}
          register={register}
        />
      ))}
    </group>
  )
}

function Label({ remnant, active, refFn }: { remnant: Remnant; active: boolean; refFn: (el: HTMLDivElement | null) => void }) {
  return (
    <div
      ref={refFn}
      className={clsx(
        'pointer-events-none absolute left-0 top-0 whitespace-nowrap rounded-md border px-2 py-1 font-mono text-[11px] leading-none tabular-nums shadow-lg backdrop-blur-md transition-[background-color,color,border-color] duration-200',
        active
          ? 'z-20 border-reclaim-400 bg-reclaim-400 text-graphite-950'
          : 'z-10 border-reclaim-400/40 bg-graphite-950/80 text-reclaim-300',
      )}
      style={{ opacity: 0 }}
    >
      <span className="font-medium">{remnant.id.split('-').pop()}</span>
      <span className="mx-1.5 opacity-50">·</span>
      {fmtMm(remnant.width)} × {fmtMm(remnant.height)}
      {remnant.weight_kg !== null && (
        <>
          <span className="mx-1.5 opacity-50">·</span>
          {fmtKg(remnant.weight_kg)} kg
        </>
      )}
    </div>
  )
}

export default function SheetViewer(props: SheetViewerProps) {
  const distance = SCENE_SIZE * 1.42
  const anchors = useRef(new Map<string, THREE.Object3D>())
  const labels = useRef(new Map<string, HTMLDivElement>())

  const register = useCallback<Register>((id, anchor) => {
    if (anchor) anchors.current.set(id, anchor)
    else anchors.current.delete(id)
  }, [])

  const shown = useMemo(() => {
    const top = [...props.sheet.remnants].sort((a, b) => b.area_m2 - a.area_m2).slice(0, RESTING_LABELS)
    const extra = props.sheet.remnants.find((r) => r.id === props.highlighted)
    return extra && !top.includes(extra) ? [...top, extra] : top
  }, [props.sheet.remnants, props.highlighted])

  return (
    <div className="relative size-full">
      <Canvas
        shadows
        dpr={[1, 2]}
        camera={{ fov: 32, position: [distance * 0.38, distance * 0.6, distance * 0.86], near: 0.05, far: 200 }}
        gl={{ antialias: true, alpha: true }}
        onPointerMissed={() => props.onHighlight(null)}
      >
        <ambientLight intensity={0.3} />
        <directionalLight
          position={[6, 12, 5]}
          intensity={1.5}
          castShadow
          shadow-mapSize={[2048, 2048]}
          shadow-camera-left={-8}
          shadow-camera-right={8}
          shadow-camera-top={8}
          shadow-camera-bottom={-8}
        />
        <directionalLight position={[-8, 4, -6]} intensity={0.3} color="#ffd2bd" />

        {/* A small procedural studio: reflections without downloading an HDR file. */}
        <Environment resolution={256} frames={1}>
          {/* Key panel sits off-axis so a top-down camera does not see its mirror image. */}
          <Lightformer form="rect" intensity={2.2} position={[-4, 6, -6]} rotation-x={Math.PI / 2.6} scale={[14, 4, 1]} />
          <Lightformer form="rect" intensity={1.2} position={[-6, 2, 3]} rotation-y={Math.PI / 2} scale={[8, 2, 1]} />
          <Lightformer form="rect" intensity={0.9} position={[6, 2, 3]} rotation-y={-Math.PI / 2} scale={[8, 2, 1]} />
          <Lightformer form="rect" intensity={0.35} color="#ff8a55" position={[0, 1.5, -7]} scale={[10, 1, 1]} />
        </Environment>

        <Sheet {...props} register={register} />

        <ContactShadows position={[0, -0.02, 0]} opacity={0.55} scale={SCENE_SIZE * 1.6} blur={2.6} far={4} />
        <OrbitControls
          makeDefault
          enableDamping
          dampingFactor={0.08}
          minDistance={3}
          maxDistance={34}
          maxPolarAngle={Math.PI / 2.08}
        />
        <CameraRig mode={props.mode} distance={distance} />
        <LabelProjector anchors={anchors} labels={labels} />
      </Canvas>

      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {shown.map((r) => (
          <Label
            key={r.id}
            remnant={r}
            active={props.highlighted === r.id}
            refFn={(el) => {
              if (el) labels.current.set(r.id, el)
              else labels.current.delete(r.id)
            }}
          />
        ))}
      </div>
    </div>
  )
}
