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

// Hard mode: Simple city grid (3 rows x 7 cols)
// Buildings at EVEN columns (0, 2, 4, 6) - agent stands "in front of door"
// Roads at ODD columns (1, 3, 5) - vertical roads between buildings
// Grid layout:
// Col:  0          1      2          3      4           5      6
// Row 0: Tech Corp  road   City Bank  road   Law Office  road   Medical
// Row 1: Real Est   road   News Std   road   Accounting  road   Ins Co
// Row 2: Marketing  road   Consulting road   Engineering road   Data Ctr
const HARD_CONFIG: DifficultyConfig = {
  // Building interior config (when inside a building)
  numFloors: 4,
  floorY: {
    1: 480,  // Ground floor (sidewalk)
    2: 390,  // Second floor (first balcony)
    3: 290,  // Third floor (second balcony)
    4: 180,  // Fourth floor (top)
  },
  sideX: {
    front: 330,
    middle: 475,
    back: 620,
  },
  // Business names are dynamic based on which building is entered
  businesses: {},
  buildingImage: 'city_grid',
  buildingInteriorImage: 'building_hard',
  isMultiBuilding: false,

  // City grid configuration (3 rows x 7 cols)
  isCityGrid: true,
  cityGridRows: 3,
  cityGridCols: 7,
  agentIconSize: 80,

  // City grid positions for ALL cells (3 rows x 7 cols)
  // Buildings at EVEN columns (0, 2, 4, 6), roads at ODD columns (1, 3, 5)
  // Positions measured from the city_grid.png image scaled to 800x533
  cityGridPositions: {
    // Row 0: Tech Corp, road, City Bank, road, Law Office, road, Medical
    '0_0': { x: 150, y: 145 },  // Tech Corp
    '0_1': { x: 230, y: 145 },  // road
    '0_2': { x: 315, y: 145 },  // City Bank
    '0_3': { x: 400, y: 145 },  // road
    '0_4': { x: 480, y: 145 },  // Law Office
    '0_5': { x: 565, y: 145 },  // road
    '0_6': { x: 645, y: 145 },  // Medical
    // Row 1: Real Estate, road, News Studio, road, Accounting, road, Insurance Co
    '1_0': { x: 150, y: 295 },  // Real Estate
    '1_1': { x: 230, y: 295 },  // road
    '1_2': { x: 315, y: 295 },  // News Studio
    '1_3': { x: 400, y: 295 },  // road
    '1_4': { x: 480, y: 295 },  // Accounting
    '1_5': { x: 565, y: 295 },  // road
    '1_6': { x: 645, y: 295 },  // Insurance Co
    // Row 2: Marketing, road, Consulting, road, Engineering, road, Data Center
    '2_0': { x: 150, y: 450 },  // Marketing
    '2_1': { x: 230, y: 450 },  // road
    '2_2': { x: 315, y: 450 },  // Consulting
    '2_3': { x: 400, y: 450 },  // road
    '2_4': { x: 480, y: 450 },  // Engineering
    '2_5': { x: 565, y: 450 },  // road
    '2_6': { x: 645, y: 450 },  // Data Center
  },

  // Building names at each grid position (EVEN columns only)
  cityBuildings: {
    '0_0': 'Tech Corp',
    '0_2': 'City Bank',
    '0_4': 'Law Office',
    '0_6': 'Medical',
    '1_0': 'Real Estate',
    '1_2': 'News Studio',
    '1_4': 'Accounting',
    '1_6': 'Insurance Co',
    '2_0': 'Marketing',
    '2_2': 'Consulting',
    '2_4': 'Engineering',
    '2_6': 'Data Center',
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
