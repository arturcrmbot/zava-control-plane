/**
 * Generate evenly-distributed points on a unit sphere using the Fibonacci /
 * sunflower coil algorithm. This is the same family of techniques Stripe
 * uses for their globe (see https://stripe.com/blog/globe). Spacing stays
 * consistent from pole to pole, no clumping.
 */

import * as THREE from "three";

/** Generate `n` Vector3 points on a unit sphere with Fibonacci spacing. */
export function sunflowerSphere(n: number, radius = 1): THREE.Vector3[] {
  const points: THREE.Vector3[] = [];
  const phi = Math.PI * (3 - Math.sqrt(5)); // golden angle
  for (let i = 0; i < n; i++) {
    // y goes from 1 to -1 evenly
    const y = 1 - (i / Math.max(1, n - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const theta = phi * i;
    const x = Math.cos(theta) * r;
    const z = Math.sin(theta) * r;
    points.push(new THREE.Vector3(x * radius, y * radius, z * radius));
  }
  return points;
}

/**
 * Generate `n` Vector3 points filling a unit ball (uniform inside the
 * volume). Used to seed workflow motes inside a domain orb.
 */
export function uniformBall(n: number, radius = 1): THREE.Vector3[] {
  const points: THREE.Vector3[] = [];
  for (let i = 0; i < n; i++) {
    // Rejection-free: u^(1/3) gives uniform radius distribution.
    const u = Math.random();
    const r = Math.cbrt(u) * radius;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const x = r * Math.sin(phi) * Math.cos(theta);
    const y = r * Math.sin(phi) * Math.sin(theta);
    const z = r * Math.cos(phi);
    points.push(new THREE.Vector3(x, y, z));
  }
  return points;
}

/** Random point on the surface of a unit sphere (Marsaglia). */
export function randomOnSphere(radius = 1): THREE.Vector3 {
  let x = 0;
  let y = 0;
  let z = 0;
  let s = 2;
  while (s >= 1 || s === 0) {
    x = Math.random() * 2 - 1;
    y = Math.random() * 2 - 1;
    s = x * x + y * y;
  }
  const factor = 2 * Math.sqrt(1 - s);
  z = 1 - 2 * s;
  return new THREE.Vector3(x * factor * radius, y * factor * radius, z * radius);
}
