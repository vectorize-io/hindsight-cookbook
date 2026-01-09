import Phaser from 'phaser';
import { BootScene } from './scenes/BootScene';
import { BuildingScene } from './scenes/BuildingScene';

// Game dimensions (3:2 aspect ratio to match building image)
export const GAME_WIDTH = 800;
export const GAME_HEIGHT = 533;

export const gameConfig: Phaser.Types.Core.GameConfig = {
  type: Phaser.AUTO,
  width: GAME_WIDTH,
  height: GAME_HEIGHT,
  backgroundColor: '#87CEEB',
  parent: 'phaser-container',
  scene: [BootScene, BuildingScene],
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
};

// Total floors in the building
export const NUM_FLOORS = 3;

// Floor Y positions (mapped to building_easy.png walkways)
export const FLOOR_Y: Record<number, number> = {
  1: 442,  // Ground floor (Reception/Mail Room)
  2: 285,  // Second floor (Accounting/Game Studio)
  3: 155,  // Top floor (Tech Lab/Cafe) - adjusted to sit on balcony
};

// Side X positions (mapped to door positions in image)
export const SIDE_X: Record<string, number> = {
  front: 155,   // Left side doors
  middle: 400,  // Center elevator
  back: 645,    // Right side doors
};

// Business names per floor/side (matching the building image labels)
export const BUSINESSES: Record<string, string> = {
  '1_front': 'Reception',
  '1_back': 'Mail Room',
  '2_front': 'Accounting',
  '2_back': 'Game Studio',
  '3_front': 'Tech Lab',
  '3_back': 'Cafe',
};
