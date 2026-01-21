import { useEffect, useRef, useCallback } from 'react';
import Phaser from 'phaser';
import { gameConfig } from './config';
import { useGameStore } from '../stores/gameStore';

interface PhaserGameProps {
  floor: number;
  side: string;
  isThinking: boolean;
  packageText: string;
  deliverySuccess: boolean;
  deliveryFailed: boolean;
  deliveryCancelled: boolean;
  lastActionTool?: string;  // Tool name of the most recent action
  difficulty?: 'easy' | 'medium' | 'hard';
  // Hard mode city grid props
  gridRow?: number;
  gridCol?: number;
  currentBuilding?: string | null;
}

interface MoveCommand {
  floor: number;
  side: string;
}

interface GridCommand {
  type: 'move_grid' | 'enter_building' | 'exit_building';
  row?: number;
  col?: number;
  buildingName?: string;
}

export function PhaserGame({ floor, side, isThinking, packageText, deliverySuccess, deliveryFailed, deliveryCancelled, lastActionTool, difficulty = 'easy', gridRow = 0, gridCol = 0, currentBuilding = null }: PhaserGameProps) {
  const gameRef = useRef<Phaser.Game | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const lastFloorRef = useRef(floor);
  const lastSideRef = useRef(side);
  const lastSuccessRef = useRef(false);
  const lastFailedRef = useRef(false);
  const lastCancelledRef = useRef(false);
  const setAnimating = useGameStore((state) => state.setAnimating);

  // Hard mode grid refs
  const lastGridRowRef = useRef(gridRow);
  const lastGridColRef = useRef(gridCol);
  const lastBuildingRef = useRef<string | null>(currentBuilding);

  // Animation queues
  const moveQueueRef = useRef<MoveCommand[]>([]);
  const gridQueueRef = useRef<GridCommand[]>([]);  // For city grid animations
  const effectQueueRef = useRef<string[]>([]);  // For non-movement animations
  const isAnimatingRef = useRef(false);

  // Process next move in queue
  const processNextMove = useCallback((customDelay?: number) => {
    // First check grid queue (hard mode city navigation)
    if (gridQueueRef.current.length > 0) {
      isAnimatingRef.current = true;
      setAnimating(true);
      const gridCmd = gridQueueRef.current.shift()!;

      if (gridCmd.type === 'move_grid') {
        window.dispatchEvent(new CustomEvent('game-event', {
          detail: { type: 'move_agent_grid', payload: { row: gridCmd.row, col: gridCmd.col } }
        }));
      } else if (gridCmd.type === 'enter_building') {
        window.dispatchEvent(new CustomEvent('game-event', {
          detail: { type: 'enter_building', payload: { buildingName: gridCmd.buildingName } }
        }));
      } else if (gridCmd.type === 'exit_building') {
        window.dispatchEvent(new CustomEvent('game-event', {
          detail: { type: 'exit_building', payload: {} }
        }));
      }
      return;
    }

    // Then check move queue (building navigation)
    if (moveQueueRef.current.length > 0) {
      isAnimatingRef.current = true;
      setAnimating(true);
      const nextMove = moveQueueRef.current.shift()!;

      window.dispatchEvent(new CustomEvent('game-event', {
        detail: { type: 'move_agent', payload: { floor: nextMove.floor, side: nextMove.side } }
      }));
      return;
    }

    // Then check effect queue (reading animations, success, etc.)
    if (effectQueueRef.current.length > 0) {
      isAnimatingRef.current = true;
      setAnimating(true);
      const effect = effectQueueRef.current.shift()!;

      window.dispatchEvent(new CustomEvent('game-event', {
        detail: { type: effect }
      }));

      // Different durations for different effects
      let effectDuration = 1400; // Default for reading animation
      let postEffectDelay = 200; // Standard pause between animations

      if (effect === 'delivery_success' || effect === 'delivery_failed') {
        effectDuration = 2500; // Success/failure animation is longer
        postEffectDelay = 500; // Longer pause after delivery end before reset

        // Queue reset animation to return to starting position (for easy mode: floor 1, front)
        // This happens after the success/failure animation
        setTimeout(() => {
          if (difficulty === 'easy') {
            moveQueueRef.current.push({ floor: 1, side: 'front' });
          } else if (difficulty === 'medium') {
            moveQueueRef.current.push({ floor: 1, side: 'building_a' });
          }
          // For hard mode, reset is handled differently (grid position)
          window.dispatchEvent(new CustomEvent('animation-complete', { detail: { delay: postEffectDelay } }));
        }, effectDuration);
        return;
      }

      setTimeout(() => {
        window.dispatchEvent(new CustomEvent('animation-complete'));
      }, effectDuration);
      return;
    }

    // Nothing left to process
    isAnimatingRef.current = false;
    setAnimating(false);
  }, [setAnimating, difficulty]);

  // Listen for animation complete events from Phaser
  useEffect(() => {
    const handleAnimationComplete = (event: Event) => {
      const customEvent = event as CustomEvent;
      const delay = customEvent.detail?.delay ?? 200; // Default 0.2s pause between animations
      setTimeout(() => {
        processNextMove();
      }, delay);
    };

    window.addEventListener('animation-complete', handleAnimationComplete);
    return () => window.removeEventListener('animation-complete', handleAnimationComplete);
  }, [processNextMove]);

  // Track initial difficulty for scene-ready handler
  const initialDifficultyRef = useRef(difficulty);
  initialDifficultyRef.current = difficulty;

  // Initialize Phaser game (only once)
  useEffect(() => {
    if (!containerRef.current || gameRef.current) return;

    // Handler for when BuildingScene signals it's ready
    const handleSceneReady = () => {
      window.dispatchEvent(new CustomEvent('game-event', {
        detail: { type: 'set_difficulty', payload: { difficulty: initialDifficultyRef.current } }
      }));
      window.removeEventListener('scene-ready', handleSceneReady);
    };

    window.addEventListener('scene-ready', handleSceneReady);

    gameRef.current = new Phaser.Game({
      ...gameConfig,
      parent: containerRef.current,
    });

    return () => {
      window.removeEventListener('scene-ready', handleSceneReady);
      if (gameRef.current) {
        gameRef.current.destroy(true);
        gameRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handle floor/side changes - queue moves instead of dispatching directly
  useEffect(() => {
    if (floor !== lastFloorRef.current || side !== lastSideRef.current) {
      lastFloorRef.current = floor;
      lastSideRef.current = side;

      // Add to queue
      moveQueueRef.current.push({ floor, side });

      // Start processing if not already animating
      if (!isAnimatingRef.current) {
        processNextMove();
      }
    }
  }, [floor, side, processNextMove]);

  // Handle thinking state
  useEffect(() => {
    window.dispatchEvent(new CustomEvent('game-event', {
      detail: { type: 'set_thinking', payload: { thinking: isThinking } }
    }));
  }, [isThinking]);

  // Handle package text
  useEffect(() => {
    window.dispatchEvent(new CustomEvent('game-event', {
      detail: { type: 'set_package', payload: { text: packageText } }
    }));
  }, [packageText]);

  // Handle delivery success - clear other effects and play immediately after moves
  useEffect(() => {
    if (deliverySuccess && !lastSuccessRef.current) {
      // Immediately mark as animating to prevent thinking animation from showing
      isAnimatingRef.current = true;
      setAnimating(true);

      // Clear any pending non-essential animations (like show_reading)
      effectQueueRef.current = effectQueueRef.current.filter(
        e => e === 'delivery_success' || e === 'delivery_failed'
      );
      // Queue the success animation
      effectQueueRef.current.push('delivery_success');

      // Start processing
      processNextMove();
    }
    lastSuccessRef.current = deliverySuccess;
  }, [deliverySuccess, processNextMove, setAnimating]);

  // Handle delivery failure - clear other effects and play immediately after moves
  useEffect(() => {
    if (deliveryFailed && !lastFailedRef.current) {
      // Immediately mark as animating to prevent thinking animation from showing
      isAnimatingRef.current = true;
      setAnimating(true);

      // Clear any pending non-essential animations (like show_reading)
      effectQueueRef.current = effectQueueRef.current.filter(
        e => e === 'delivery_success' || e === 'delivery_failed'
      );
      // Queue the failure animation
      effectQueueRef.current.push('delivery_failed');

      // Start processing
      processNextMove();
    }
    lastFailedRef.current = deliveryFailed;
  }, [deliveryFailed, processNextMove, setAnimating]);

  // Handle delivery cancelled - immediately clear all queues and reset
  useEffect(() => {
    if (deliveryCancelled && !lastCancelledRef.current) {
      // Clear ALL animation queues immediately
      moveQueueRef.current = [];
      gridQueueRef.current = [];
      effectQueueRef.current = [];
      isAnimatingRef.current = false;

      // Queue reset animation based on difficulty
      if (difficulty === 'easy') {
        moveQueueRef.current.push({ floor: 1, side: 'front' });
      } else if (difficulty === 'medium') {
        moveQueueRef.current.push({ floor: 1, side: 'building_a' });
      } else if (difficulty === 'hard') {
        // Hard mode: reset to starting grid position
        gridQueueRef.current.push({ type: 'exit_building' });
        gridQueueRef.current.push({ type: 'move_grid', row: 0, col: 0 });
      }

      // Start reset animation immediately
      processNextMove();
    }
    lastCancelledRef.current = deliveryCancelled;
  }, [deliveryCancelled, processNextMove, difficulty]);

  // Handle difficulty changes
  const lastDifficultyRef = useRef(difficulty);
  useEffect(() => {
    if (difficulty !== lastDifficultyRef.current) {
      lastDifficultyRef.current = difficulty;
      window.dispatchEvent(new CustomEvent('game-event', {
        detail: { type: 'set_difficulty', payload: { difficulty } }
      }));
    }
  }, [difficulty]);

  // Handle hard mode grid position changes
  useEffect(() => {
    if (difficulty !== 'hard') return;

    // Check if building state changed (entering or exiting building)
    if (currentBuilding !== lastBuildingRef.current) {
      if (currentBuilding && !lastBuildingRef.current) {
        // Entering a building
        gridQueueRef.current.push({
          type: 'enter_building',
          buildingName: currentBuilding,
        });

        if (!isAnimatingRef.current) {
          processNextMove();
        }
      } else if (!currentBuilding && lastBuildingRef.current) {
        // Exiting a building
        gridQueueRef.current.push({
          type: 'exit_building',
        });

        if (!isAnimatingRef.current) {
          processNextMove();
        }
      }
      lastBuildingRef.current = currentBuilding;
    }

    // Check if grid position changed (while on street)
    if (!currentBuilding && (gridRow !== lastGridRowRef.current || gridCol !== lastGridColRef.current)) {
      gridQueueRef.current.push({
        type: 'move_grid',
        row: gridRow,
        col: gridCol,
      });

      if (!isAnimatingRef.current) {
        processNextMove();
      }

      lastGridRowRef.current = gridRow;
      lastGridColRef.current = gridCol;
    }
  }, [gridRow, gridCol, currentBuilding, difficulty, processNextMove]);

  // Handle special action animations (like reading employee list)
  // Don't queue reading animation if delivery has already completed
  const lastActionToolRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    // Skip if delivery is already done - don't play reading animation after success/failure
    if (deliverySuccess || deliveryFailed) {
      return;
    }

    // Skip if delivery completion is already queued
    const hasDeliveryEnd = effectQueueRef.current.some(
      e => e === 'delivery_success' || e === 'delivery_failed'
    );
    if (hasDeliveryEnd) {
      return;
    }

    if (lastActionTool && lastActionTool !== lastActionToolRef.current) {
      lastActionToolRef.current = lastActionTool;

      if (lastActionTool === 'get_employee_list') {
        // Queue the reading animation to play after current animations
        effectQueueRef.current.push('show_reading');

        // If not currently animating, start processing
        if (!isAnimatingRef.current) {
          processNextMove();
        }
      }
    }
  }, [lastActionTool, processNextMove, deliverySuccess, deliveryFailed]);

  // Reset lastActionToolRef when delivery ends so it's fresh for next delivery
  useEffect(() => {
    if (!deliverySuccess && !deliveryFailed) {
      // New delivery starting - reset the tool tracking
      lastActionToolRef.current = undefined;
    }
  }, [deliverySuccess, deliveryFailed]);

  return (
    <div
      ref={containerRef}
      id="phaser-container"
      className="w-full rounded-lg overflow-hidden"
      style={{ aspectRatio: '800/533' }}
    />
  );
}
