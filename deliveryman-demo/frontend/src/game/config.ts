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
    expandParent: false,
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
  // Hard mode city grid properties
  isCityGrid?: boolean;
  cityGridRows?: number;
  cityGridCols?: number;
  cityGridPositions?: Record<string, { x: number; y: number }>;
  cityBuildings?: Record<string, string>;
  buildingInteriorImage?: string;
  agentIconSize?: number;
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
// Image is 2048x1365 scaled to 800x533
const MEDIUM_CONFIG: DifficultyConfig = {
  numFloors: 4,
  floorY: {
    1: 510,  // Ground floor (Lobby/Storage/IT Support)
    2: 395,  // Second floor (Game Studio/Archives/Accounting)
    3: 290,  // Third floor - bridge level (Exec Suite/Marketing/Sales)
    4: 195,  // Top floor (Reception/Cafe/HR Dept)
  },
  sideX: {
    building_a: 175,   // Left building (Lobby column)
    building_b: 415,   // Center building (Storage column)
    building_c: 655,   // Right building (IT Support column)
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

// Hard mode: City grid with 12 buildings (4 rows x 3 cols)
// Agent navigates streets, enters buildings, then delivers on 5 floors
const HARD_CONFIG: DifficultyConfig = {
  // Building interior config (when inside a building)
  numFloors: 5,
  floorY: {
    1: 460,  // Ground floor
    2: 365,  // Second floor
    3: 275,  // Third floor
    4: 185,  // Fourth floor
    5: 95,   // Fifth floor (top)
  },
  sideX: {
    front: 250,
    middle: 400,
    back: 550,
  },
  // Business names are dynamic based on which building is entered
  businesses: {},
  buildingImage: 'city_grid',
  buildingInteriorImage: 'building_hard',
  isMultiBuilding: false,

  // City grid configuration
  isCityGrid: true,
  cityGridRows: 4,
  cityGridCols: 3,
  agentIconSize: 40,

  // City grid positions (center of each building cell)
  // Grid is 800x533, divided into 4 rows x 3 cols
  // Each cell is roughly 267x133 pixels
  cityGridPositions: {
    '0_0': { x: 133, y: 67 },   // Row 0, Col 0
    '0_1': { x: 400, y: 67 },   // Row 0, Col 1
    '0_2': { x: 667, y: 67 },   // Row 0, Col 2
    '1_0': { x: 133, y: 200 },  // Row 1, Col 0
    '1_1': { x: 400, y: 200 },  // Row 1, Col 1
    '1_2': { x: 667, y: 200 },  // Row 1, Col 2
    '2_0': { x: 133, y: 333 },  // Row 2, Col 0
    '2_1': { x: 400, y: 333 },  // Row 2, Col 1
    '2_2': { x: 667, y: 333 },  // Row 2, Col 2
    '3_0': { x: 133, y: 466 },  // Row 3, Col 0
    '3_1': { x: 400, y: 466 },  // Row 3, Col 1
    '3_2': { x: 667, y: 466 },  // Row 3, Col 2
  },

  // Building names at each grid position (matches backend CITY_GRID)
  cityBuildings: {
    '0_0': 'Tech Corp',
    '0_1': 'City Bank',
    '0_2': 'Law Office',
    '1_0': 'Medical',
    '1_1': 'Real Estate',
    '1_2': 'News Studio',
    '2_0': 'Accounting',
    '2_1': 'Insurance Co',
    '2_2': 'Marketing',
    '3_0': 'Consulting',
    '3_1': 'Engineering',
    '3_2': 'Data Center',
  },
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
