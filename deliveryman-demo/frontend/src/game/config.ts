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

// Difficulty-specific configurations
export type Difficulty = 'easy' | 'medium' | 'hard';

export interface DifficultyConfig {
  numFloors: number;
  floorY: Record<number, number>;
  sideX: Record<string, number>;
  businesses: Record<string, string>;
  buildingImage: string;
  isMultiBuilding: boolean;
}

// Easy mode: 3 floors, front/back layout
const EASY_CONFIG: DifficultyConfig = {
  numFloors: 3,
  floorY: {
    1: 442,  // Ground floor
    2: 285,  // Second floor
    3: 155,  // Top floor
  },
  sideX: {
    front: 155,
    middle: 400,
    back: 645,
  },
  businesses: {
    '1_front': 'Reception',
    '1_back': 'Mail Room',
    '2_front': 'Accounting',
    '2_back': 'Game Studio',
    '3_front': 'Tech Lab',
    '3_back': 'Cafe',
  },
  buildingImage: 'building_easy',
  isMultiBuilding: false,
};

// Medium mode: 4 floors, 3 buildings (A, B, C)
const MEDIUM_CONFIG: DifficultyConfig = {
  numFloors: 4,
  floorY: {
    1: 455,  // Ground floor
    2: 355,  // Second floor
    3: 255,  // Third floor (bridge level)
    4: 155,  // Top floor
  },
  sideX: {
    building_a: 135,
    building_b: 400,
    building_c: 665,
    middle: 400,  // For elevator - defaults to building B
  },
  businesses: {
    '1_building_a': 'Lobby',
    '1_building_b': 'Storage',
    '1_building_c': 'IT Support',
    '2_building_a': 'Game Studio',
    '2_building_b': 'Archives',
    '2_building_c': 'Accounting',
    '3_building_a': 'Exec Suite',
    '3_building_b': 'Marketing',
    '3_building_c': 'Sales',
    '4_building_a': 'Reception',
    '4_building_b': 'Cafe',
    '4_building_c': 'HR Dept',
  },
  buildingImage: 'building_medium',
  isMultiBuilding: true,
};

// Hard mode: 7 floors, front/back layout
const HARD_CONFIG: DifficultyConfig = {
  numFloors: 7,
  floorY: {
    1: 480,
    2: 425,
    3: 370,
    4: 315,
    5: 260,
    6: 205,
    7: 150,
  },
  sideX: {
    front: 155,
    middle: 400,
    back: 645,
  },
  businesses: {
    '1_front': 'Reception Hall',
    '1_back': 'Package Center',
    '2_front': 'Administration',
    '2_back': 'IT Support',
    '3_front': 'Advertising Agency',
    '3_back': 'Photography Studio',
    '4_front': 'Law Firm',
    '4_back': 'Consulting Group',
    '5_front': 'Software Company',
    '5_back': 'Data Science Lab',
    '6_front': 'News Station',
    '6_back': 'Podcast Studio',
    '7_front': 'Corporate Headquarters',
    '7_back': 'Investor Relations',
  },
  buildingImage: 'building_easy',  // TODO: Add building_hard.png
  isMultiBuilding: false,
};

export const DIFFICULTY_CONFIGS: Record<Difficulty, DifficultyConfig> = {
  easy: EASY_CONFIG,
  medium: MEDIUM_CONFIG,
  hard: HARD_CONFIG,
};

// Legacy exports for backwards compatibility (default to easy)
export const NUM_FLOORS = 3;
export const FLOOR_Y = EASY_CONFIG.floorY;
export const SIDE_X = EASY_CONFIG.sideX;
export const BUSINESSES = EASY_CONFIG.businesses;
