import Phaser from 'phaser';
import { GAME_WIDTH, GAME_HEIGHT, FLOOR_Y, SIDE_X, BUSINESSES } from '../config';

export class BuildingScene extends Phaser.Scene {
  private agent!: Phaser.GameObjects.Container;
  private agentSprite!: Phaser.GameObjects.Image;
  private thinkingIndicator!: Phaser.GameObjects.Container;
  private floorText!: Phaser.GameObjects.Text;
  private locationText!: Phaser.GameObjects.Text;
  private packageText!: Phaser.GameObjects.Text;

  private currentFloor: number = 1;
  private currentSide: string = 'front';
  private isMoving: boolean = false;

  constructor() {
    super({ key: 'BuildingScene' });
  }

  create() {
    // Add building background sprite
    const building = this.add.image(GAME_WIDTH / 2, GAME_HEIGHT / 2, 'building');
    building.setDisplaySize(GAME_WIDTH, GAME_HEIGHT);

    // Create agent container
    this.agent = this.add.container(SIDE_X.front, FLOOR_Y[1]);

    // Agent sprite
    this.agentSprite = this.add.image(0, 0, 'agent');
    this.agentSprite.setScale(0.85);
    this.agentSprite.setOrigin(0.5, 1);
    this.agent.add(this.agentSprite);

    // Thinking indicator
    this.thinkingIndicator = this.add.container(0, -55);
    const thinkBg = this.add.circle(0, 0, 15, 0xFCD34D, 0.95);
    const thinkText = this.add.text(0, 0, '🤔', { fontSize: '16px' });
    thinkText.setOrigin(0.5, 0.5);
    this.thinkingIndicator.add([thinkBg, thinkText]);
    this.thinkingIndicator.setVisible(false);
    this.agent.add(this.thinkingIndicator);

    // UI Overlays
    this.floorText = this.add.text(12, 12, 'Floor 1', {
      fontSize: '16px',
      fontFamily: 'Arial, sans-serif',
      color: '#ffffff',
      backgroundColor: '#1e293b',
      padding: { x: 10, y: 6 },
    }).setDepth(100);

    this.locationText = this.add.text(GAME_WIDTH - 12, 12, 'Reception', {
      fontSize: '13px',
      fontFamily: 'Arial, sans-serif',
      color: '#4ade80',
      backgroundColor: '#1e293b',
      padding: { x: 10, y: 6 },
    }).setOrigin(1, 0).setDepth(100);

    this.packageText = this.add.text(GAME_WIDTH / 2, GAME_HEIGHT - 8, '', {
      fontSize: '12px',
      fontFamily: 'Arial, sans-serif',
      color: '#fbbf24',
      backgroundColor: '#1e293bdd',
      padding: { x: 12, y: 6 },
    }).setOrigin(0.5, 1).setVisible(false).setDepth(100);

    // Start idle animation
    this.startIdleAnimation();

    // Listen for game events from React
    window.addEventListener('game-event', this.handleGameEvent.bind(this) as EventListener);
  }

  private handleGameEvent(event: CustomEvent) {
    const { type, payload } = event.detail;

    switch (type) {
      case 'move_agent':
        this.moveAgent(payload.floor, payload.side);
        break;
      case 'set_thinking':
        this.setThinking(payload.thinking);
        break;
      case 'set_package':
        this.setPackage(payload.text);
        break;
      case 'delivery_success':
        this.showSuccess();
        break;
      case 'delivery_failed':
        this.showFailure();
        break;
      case 'show_reading':
        this.showReading();
        break;
    }
  }

  private startIdleAnimation() {
    this.tweens.add({
      targets: this.agentSprite,
      y: -2,
      duration: 800,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut',
    });
  }

  private stopIdleAnimation() {
    this.tweens.killTweensOf(this.agentSprite);
    this.agentSprite.y = 0;
  }

  public moveAgent(floor: number, side: string) {
    // With the animation queue in PhaserGame, this should not be called while moving
    // But as a safety fallback, we just return if already moving
    if (this.isMoving) return;

    const targetX = SIDE_X[side] || SIDE_X.middle;
    const targetY = FLOOR_Y[floor] || FLOOR_Y[1];

    const sameFloor = floor === this.currentFloor;
    const sameSide = side === this.currentSide;

    if (sameFloor && sameSide) {
      // No move needed, but still signal completion
      window.dispatchEvent(new CustomEvent('animation-complete'));
      return;
    }

    this.isMoving = true;
    this.stopIdleAnimation();

    // Set facing direction
    if (targetX < this.agent.x) {
      this.agentSprite.setFlipX(true);
    } else if (targetX > this.agent.x) {
      this.agentSprite.setFlipX(false);
    }

    const finishMove = () => {
      this.isMoving = false;
      this.startIdleAnimation();
      // Signal that animation is complete so next queued move can start
      window.dispatchEvent(new CustomEvent('animation-complete'));
    };

    if (sameFloor) {
      // Just walk horizontally
      this.walkTo(targetX, () => {
        this.currentSide = side;
        this.updateUI();
        finishMove();
      });
    } else {
      // Walk to elevator, then move vertically, then walk to target
      this.walkTo(SIDE_X.middle, () => {
        // Fade out for elevator
        this.tweens.add({
          targets: this.agent,
          alpha: 0,
          duration: 200,
          onComplete: () => {
            // Move to new floor
            this.agent.y = targetY;
            this.currentFloor = floor;

            // Fade back in
            this.tweens.add({
              targets: this.agent,
              alpha: 1,
              duration: 200,
              delay: 300, // Simulate elevator travel time
              onComplete: () => {
                this.updateUI();

                if (side !== 'middle') {
                  // Set facing direction for final walk
                  if (SIDE_X[side] < this.agent.x) {
                    this.agentSprite.setFlipX(true);
                  } else {
                    this.agentSprite.setFlipX(false);
                  }

                  this.walkTo(targetX, () => {
                    this.currentSide = side;
                    this.updateUI();
                    finishMove();
                  });
                } else {
                  this.currentSide = 'middle';
                  this.updateUI();
                  finishMove();
                }
              },
            });
          },
        });
      });
    }
  }

  private walkTo(targetX: number, onComplete: () => void) {
    const distance = Math.abs(targetX - this.agent.x);
    const duration = distance * 3; // Slightly slower for smoother look

    // Walking bob animation
    this.tweens.add({
      targets: this.agentSprite,
      y: -3,
      duration: 100,
      yoyo: true,
      repeat: Math.floor(duration / 200),
      ease: 'Linear',
    });

    this.tweens.add({
      targets: this.agent,
      x: targetX,
      duration: duration,
      ease: 'Linear',
      onComplete: () => {
        this.agentSprite.y = 0;
        onComplete();
      },
    });
  }

  private updateUI() {
    this.floorText.setText(`Floor ${this.currentFloor}`);

    const key = `${this.currentFloor}_${this.currentSide}`;
    const locationName = BUSINESSES[key] || (this.currentSide === 'middle' ? 'Elevator' : 'Unknown');
    this.locationText.setText(locationName);
  }

  public setThinking(thinking: boolean) {
    this.thinkingIndicator.setVisible(thinking);

    if (thinking) {
      this.tweens.add({
        targets: this.thinkingIndicator,
        scaleX: 1.15,
        scaleY: 1.15,
        duration: 400,
        yoyo: true,
        repeat: -1,
        ease: 'Sine.easeInOut',
      });
    } else {
      this.tweens.killTweensOf(this.thinkingIndicator);
      this.thinkingIndicator.setScale(1);
    }
  }

  public setPackage(text: string) {
    if (text) {
      this.packageText.setText(`📦 Delivering to: ${text}`);
      this.packageText.setVisible(true);
    } else {
      this.packageText.setVisible(false);
    }
  }

  public showReading() {
    // Show a clipboard/reading indicator above the agent
    const clipboardBg = this.add.rectangle(
      this.agent.x + 25,
      this.agent.y - 60,
      32,
      40,
      0x8B4513,  // Brown clipboard
      0.95
    );
    clipboardBg.setStrokeStyle(2, 0x5D3A1A);

    // Paper on clipboard
    const paper = this.add.rectangle(
      this.agent.x + 25,
      this.agent.y - 58,
      26,
      32,
      0xFFFFFF,
      0.95
    );

    // Lines on paper (representing text)
    const lines: Phaser.GameObjects.Rectangle[] = [];
    for (let i = 0; i < 4; i++) {
      const line = this.add.rectangle(
        this.agent.x + 25,
        this.agent.y - 70 + (i * 8),
        18,
        2,
        0x666666,
        0.8
      );
      lines.push(line);
    }

    // Clipboard clip
    const clip = this.add.rectangle(
      this.agent.x + 25,
      this.agent.y - 78,
      12,
      6,
      0xC0C0C0,
      1
    );

    // Group all elements
    const elements = [clipboardBg, paper, ...lines, clip];

    // Animate in
    elements.forEach(el => {
      el.setAlpha(0);
      el.setScale(0.5);
    });

    this.tweens.add({
      targets: elements,
      alpha: 1,
      scaleX: 1,
      scaleY: 1,
      duration: 200,
      ease: 'Back.easeOut',
    });

    // Hold for a moment, then animate out
    this.time.delayedCall(800, () => {
      this.tweens.add({
        targets: elements,
        alpha: 0,
        y: '-=20',
        duration: 300,
        ease: 'Quad.easeIn',
        onComplete: () => {
          elements.forEach(el => el.destroy());
        },
      });
    });
  }

  public showSuccess() {
    // Stop idle animation for celebration
    this.stopIdleAnimation();

    // === SUCCESS BANNER at top ===
    const bannerY = 60;

    // Glow background
    const glow = this.add.rectangle(GAME_WIDTH / 2, bannerY, 300, 50, 0x4ade80, 0.3);
    glow.setBlendMode(Phaser.BlendModes.ADD);

    // Main banner background
    const banner = this.add.rectangle(GAME_WIDTH / 2, bannerY, 280, 45, 0x1e293b, 0.95);
    banner.setStrokeStyle(3, 0x4ade80);

    // SUCCESS text
    const successText = this.add.text(GAME_WIDTH / 2, bannerY, 'SUCCESS!', {
      fontSize: '28px',
      fontFamily: 'Arial Black, sans-serif',
      color: '#4ade80',
      stroke: '#166534',
      strokeThickness: 2,
    }).setOrigin(0.5, 0.5);

    // Sparkle decorations
    const sparklePositions = [
      { x: -120, y: -5 }, { x: 120, y: -5 },
      { x: -100, y: 10 }, { x: 100, y: 10 },
    ];
    const sparkles: Phaser.GameObjects.Text[] = [];
    sparklePositions.forEach(pos => {
      const sparkle = this.add.text(GAME_WIDTH / 2 + pos.x, bannerY + pos.y, '✦', {
        fontSize: '16px',
        color: '#fbbf24',
      }).setOrigin(0.5, 0.5);
      sparkles.push(sparkle);
    });

    // Group banner elements
    const bannerElements = [glow, banner, successText, ...sparkles];

    // Animate banner in - scale and fade
    bannerElements.forEach(el => {
      el.setAlpha(0);
      el.setScale(0.5);
    });

    this.tweens.add({
      targets: bannerElements,
      alpha: 1,
      scaleX: 1,
      scaleY: 1,
      duration: 300,
      ease: 'Back.easeOut',
    });

    // Sparkle twinkle animation
    this.tweens.add({
      targets: sparkles,
      alpha: 0.3,
      duration: 200,
      yoyo: true,
      repeat: 5,
      ease: 'Sine.easeInOut',
    });

    // Glow pulse
    this.tweens.add({
      targets: glow,
      scaleX: 1.2,
      scaleY: 1.3,
      alpha: 0.5,
      duration: 400,
      yoyo: true,
      repeat: 2,
      ease: 'Sine.easeInOut',
    });

    // Fade out banner after delay
    this.time.delayedCall(2000, () => {
      this.tweens.add({
        targets: bannerElements,
        alpha: 0,
        y: '-=20',
        duration: 400,
        ease: 'Quad.easeIn',
        onComplete: () => bannerElements.forEach(el => el.destroy()),
      });
    });

    // === AGENT CELEBRATION BOUNCE ===
    // Squash before jump
    this.tweens.add({
      targets: this.agentSprite,
      scaleY: 0.75,
      scaleX: 0.95,
      duration: 100,
      ease: 'Quad.easeIn',
      onComplete: () => {
        // First big bounce
        this.tweens.add({
          targets: this.agentSprite,
          y: -35,
          scaleY: 0.95,
          scaleX: 0.8,
          duration: 250,
          ease: 'Quad.easeOut',
          onComplete: () => {
            // Come back down
            this.tweens.add({
              targets: this.agentSprite,
              y: 0,
              scaleY: 0.8,
              scaleX: 0.9,
              duration: 200,
              ease: 'Quad.easeIn',
              onComplete: () => {
                // Second smaller bounce
                this.tweens.add({
                  targets: this.agentSprite,
                  y: -15,
                  scaleY: 0.9,
                  scaleX: 0.82,
                  duration: 150,
                  ease: 'Quad.easeOut',
                  onComplete: () => {
                    // Final land
                    this.tweens.add({
                      targets: this.agentSprite,
                      y: 0,
                      scaleY: 0.85,
                      scaleX: 0.85,
                      duration: 150,
                      ease: 'Bounce.easeOut',
                      onComplete: () => {
                        // Resume idle
                        this.startIdleAnimation();
                      },
                    });
                  },
                });
              },
            });
          },
        });
      },
    });

    // === CONFETTI (enhanced) ===
    const colors = [0x4ade80, 0x60a5fa, 0xfbbf24, 0xf472b6, 0xa78bfa];

    for (let i = 0; i < 35; i++) {
      const particle = this.add.rectangle(
        this.agent.x + Phaser.Math.Between(-40, 40),
        this.agent.y - 50,
        Phaser.Math.Between(4, 10),
        Phaser.Math.Between(4, 10),
        Phaser.Utils.Array.GetRandom(colors)
      );

      this.tweens.add({
        targets: particle,
        y: particle.y + Phaser.Math.Between(80, 150),
        x: particle.x + Phaser.Math.Between(-50, 50),
        rotation: Phaser.Math.Between(0, 8),
        alpha: 0,
        duration: Phaser.Math.Between(600, 1100),
        ease: 'Quad.easeOut',
        delay: Phaser.Math.Between(0, 200),
        onComplete: () => particle.destroy(),
      });
    }
  }

  public showFailure() {
    // === FAILURE BANNER at top ===
    const bannerY = 60;

    // Glow background (red)
    const glow = this.add.rectangle(GAME_WIDTH / 2, bannerY, 300, 50, 0xef4444, 0.3);
    glow.setBlendMode(Phaser.BlendModes.ADD);

    // Main banner background
    const banner = this.add.rectangle(GAME_WIDTH / 2, bannerY, 280, 45, 0x1e293b, 0.95);
    banner.setStrokeStyle(3, 0xef4444);

    // FAILED text
    const failedText = this.add.text(GAME_WIDTH / 2, bannerY, 'FAILED', {
      fontSize: '28px',
      fontFamily: 'Arial Black, sans-serif',
      color: '#ef4444',
      stroke: '#7f1d1d',
      strokeThickness: 2,
    }).setOrigin(0.5, 0.5);

    // X marks instead of sparkles
    const xPositions = [
      { x: -110, y: 0 }, { x: 110, y: 0 },
    ];
    const xMarks: Phaser.GameObjects.Text[] = [];
    xPositions.forEach(pos => {
      const xMark = this.add.text(GAME_WIDTH / 2 + pos.x, bannerY + pos.y, '✕', {
        fontSize: '20px',
        color: '#fca5a5',
      }).setOrigin(0.5, 0.5);
      xMarks.push(xMark);
    });

    // Group banner elements
    const bannerElements = [glow, banner, failedText, ...xMarks];

    // Animate banner in - shake effect
    bannerElements.forEach(el => {
      el.setAlpha(0);
      el.setScale(0.5);
    });

    this.tweens.add({
      targets: bannerElements,
      alpha: 1,
      scaleX: 1,
      scaleY: 1,
      duration: 200,
      ease: 'Back.easeOut',
      onComplete: () => {
        // Shake effect
        this.tweens.add({
          targets: bannerElements,
          x: '-=5',
          duration: 50,
          yoyo: true,
          repeat: 5,
          ease: 'Linear',
        });
      }
    });

    // Glow pulse
    this.tweens.add({
      targets: glow,
      scaleX: 1.2,
      scaleY: 1.3,
      alpha: 0.5,
      duration: 300,
      yoyo: true,
      repeat: 2,
      ease: 'Sine.easeInOut',
    });

    // Fade out banner after delay
    this.time.delayedCall(2000, () => {
      this.tweens.add({
        targets: bannerElements,
        alpha: 0,
        y: '-=20',
        duration: 400,
        ease: 'Quad.easeIn',
        onComplete: () => bannerElements.forEach(el => el.destroy()),
      });
    });
  }

  shutdown() {
    window.removeEventListener('game-event', this.handleGameEvent.bind(this) as EventListener);
  }
}
