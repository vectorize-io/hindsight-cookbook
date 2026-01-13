import Phaser from 'phaser';

export class BootScene extends Phaser.Scene {
  constructor() {
    super({ key: 'BootScene' });
  }

  preload() {
    // Create loading bar
    const width = this.cameras.main.width;
    const height = this.cameras.main.height;

    const progressBar = this.add.graphics();
    const progressBox = this.add.graphics();
    progressBox.fillStyle(0x222222, 0.8);
    progressBox.fillRect(width / 2 - 160, height / 2 - 25, 320, 50);

    const loadingText = this.add.text(width / 2, height / 2 - 50, 'Loading...', {
      font: '20px monospace',
      color: '#ffffff',
    });
    loadingText.setOrigin(0.5, 0.5);

    this.load.on('progress', (value: number) => {
      progressBar.clear();
      progressBar.fillStyle(0x4ade80, 1);
      progressBar.fillRect(width / 2 - 150, height / 2 - 15, 300 * value, 30);
    });

    this.load.on('complete', () => {
      progressBar.destroy();
      progressBox.destroy();
      loadingText.destroy();
    });

    // Load building sprites for all difficulties
    this.load.image('building_easy', '/sprites/building_easy.png');
    this.load.image('building_medium', '/sprites/building_medium.png');
    // Hard mode: city grid view and building interior
    this.load.image('city_grid', '/sprites/city_grid.png');
    this.load.image('building_hard', '/sprites/building_hard.png');

    // Load agent sprites
    this.load.image('agent', '/sprites/agent_transparent.png');
    this.load.image('agent_icon', '/sprites/agent_icon.png');  // City grid view icon
    // Load walk animation spritesheet (6 frames, 256x1024 each)
    this.load.spritesheet('agent_walk', '/sprites/delivery_walk.png', {
      frameWidth: 256,
      frameHeight: 1024,
    });
  }

  create() {
    this.scene.start('BuildingScene');
  }
}
