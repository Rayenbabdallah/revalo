import * as THREE from 'three'

import type { MaterialFamily } from '../../lib/api'

/** Fine streaks along one axis, used as a roughness map for brushed metal. */
function brushedTexture(): THREE.CanvasTexture {
  const size = 512
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#7a7a7a'
  ctx.fillRect(0, 0, size, size)
  for (let i = 0; i < 5200; i++) {
    const y = Math.random() * size
    const x = Math.random() * size
    const len = 40 + Math.random() * 260
    const shade = 90 + Math.floor(Math.random() * 90)
    ctx.strokeStyle = `rgba(${shade},${shade},${shade},${0.05 + Math.random() * 0.12})`
    ctx.lineWidth = Math.random() < 0.85 ? 1 : 2
    ctx.beginPath()
    ctx.moveTo(x, y)
    ctx.lineTo(x + len, y + (Math.random() - 0.5) * 1.2)
    ctx.stroke()
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(0.5, 0.5)
  texture.anisotropy = 8
  return texture
}

/** Soft fibre noise for MDF and board materials. */
function fibreTexture(): THREE.CanvasTexture {
  const size = 256
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')!
  const image = ctx.createImageData(size, size)
  for (let i = 0; i < image.data.length; i += 4) {
    const v = 150 + Math.random() * 70
    image.data[i] = image.data[i + 1] = image.data[i + 2] = v
    image.data[i + 3] = 255
  }
  ctx.putImageData(image, 0, 0)
  const texture = new THREE.CanvasTexture(canvas)
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(1.5, 1.5)
  return texture
}

let brushed: THREE.CanvasTexture | null = null
let fibre: THREE.CanvasTexture | null = null

export interface MaterialSet {
  stock: THREE.Material
  part: THREE.Material
  remnant: THREE.MeshStandardMaterial
}

export function createMaterials(family: MaterialFamily | null): MaterialSet {
  if (family === 'wood') {
    fibre ??= fibreTexture()
    return {
      stock: new THREE.MeshStandardMaterial({
        color: '#9b7552',
        roughness: 0.88,
        metalness: 0,
        roughnessMap: fibre,
        bumpMap: fibre,
        bumpScale: 0.6,
      }),
      part: new THREE.MeshStandardMaterial({ color: '#6b4d33', roughness: 0.9, metalness: 0 }),
      remnant: new THREE.MeshStandardMaterial({
        color: '#c39c70',
        roughness: 0.8,
        metalness: 0,
        roughnessMap: fibre,
        bumpMap: fibre,
        bumpScale: 0.6,
        emissive: '#c8f169',
        emissiveIntensity: 0,
      }),
    }
  }
  if (family === 'plastic') {
    return {
      stock: new THREE.MeshPhysicalMaterial({
        color: '#cfe3ee',
        roughness: 0.08,
        metalness: 0,
        transmission: 0.75,
        thickness: 0.2,
        transparent: true,
      }),
      part: new THREE.MeshStandardMaterial({ color: '#7a8a94', roughness: 0.4, transparent: true, opacity: 0.55 }),
      remnant: new THREE.MeshStandardMaterial({
        color: '#e3f3d2',
        roughness: 0.15,
        metalness: 0,
        transparent: true,
        opacity: 0.85,
        emissive: '#c8f169',
        emissiveIntensity: 0.1,
      }),
    }
  }
  brushed ??= brushedTexture()
  return {
    stock: new THREE.MeshStandardMaterial({
      color: '#8d939d',
      metalness: 0.92,
      roughness: 0.42,
      roughnessMap: brushed,
    }),
    part: new THREE.MeshStandardMaterial({ color: '#4e545e', metalness: 0.75, roughness: 0.55 }),
    remnant: new THREE.MeshStandardMaterial({
      color: '#d3d8df',
      metalness: 0.9,
      roughness: 0.28,
      roughnessMap: brushed,
      emissive: '#c8f169',
      emissiveIntensity: 0,
    }),
  }
}
