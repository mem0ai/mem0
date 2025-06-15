import * as THREE from 'three';

export interface GraphNode {
  id: string;
  position: THREE.Vector3;
  targetPosition: THREE.Vector3;
  memory: any;
  color: string;
  size: number;
}

export interface GraphEdge {
  source: string;
  target: string;
} 