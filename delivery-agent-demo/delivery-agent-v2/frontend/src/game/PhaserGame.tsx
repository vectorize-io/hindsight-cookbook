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
  lastActionTool?: string;  // Tool name of the most recent action
}

interface MoveCommand {
  floor: number;
  side: string;
}

export function PhaserGame({ floor, side, isThinking, packageText, deliverySuccess, deliveryFailed, lastActionTool }: PhaserGameProps) {
  const gameRef = useRef<Phaser.Game | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const lastFloorRef = useRef(floor);
  const lastSideRef = useRef(side);
  const lastSuccessRef = useRef(false);
  const lastFailedRef = useRef(false);
  const setAnimating = useGameStore((state) => state.setAnimating);

  // Animation queues
  const moveQueueRef = useRef<MoveCommand[]>([]);
  const effectQueueRef = useRef<string[]>([]);  // For non-movement animations
  const isAnimatingRef = useRef(false);

  // Process next move in queue
  const processNextMove = useCallback(() => {
    // First check move queue
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
      if (effect === 'delivery_success') {
        effectDuration = 2500; // Success animation is longer
      } else if (effect === 'delivery_failed') {
        effectDuration = 2500; // Failure animation duration
      }

      setTimeout(() => {
        window.dispatchEvent(new CustomEvent('animation-complete'));
      }, effectDuration);
      return;
    }

    // Nothing left to process
    isAnimatingRef.current = false;
    setAnimating(false);
  }, [setAnimating]);

  // Listen for animation complete events from Phaser
  useEffect(() => {
    const handleAnimationComplete = () => {
      processNextMove();
    };

    window.addEventListener('animation-complete', handleAnimationComplete);
    return () => window.removeEventListener('animation-complete', handleAnimationComplete);
  }, [processNextMove]);

  // Initialize Phaser game
  useEffect(() => {
    if (!containerRef.current || gameRef.current) return;

    gameRef.current = new Phaser.Game({
      ...gameConfig,
      parent: containerRef.current,
    });

    return () => {
      if (gameRef.current) {
        gameRef.current.destroy(true);
        gameRef.current = null;
      }
    };
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

  // Handle delivery success - queue it to play after all animations
  useEffect(() => {
    if (deliverySuccess && !lastSuccessRef.current) {
      // Queue the success animation to play after all other animations
      effectQueueRef.current.push('delivery_success');

      // If not currently animating, start processing
      if (!isAnimatingRef.current) {
        processNextMove();
      }
    }
    lastSuccessRef.current = deliverySuccess;
  }, [deliverySuccess, processNextMove]);

  // Handle delivery failure - queue it to play after all animations
  useEffect(() => {
    if (deliveryFailed && !lastFailedRef.current) {
      // Queue the failure animation to play after all other animations
      effectQueueRef.current.push('delivery_failed');

      // If not currently animating, start processing
      if (!isAnimatingRef.current) {
        processNextMove();
      }
    }
    lastFailedRef.current = deliveryFailed;
  }, [deliveryFailed, processNextMove]);

  // Handle special action animations (like reading employee list)
  const lastActionToolRef = useRef<string | undefined>(undefined);
  useEffect(() => {
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
  }, [lastActionTool, processNextMove]);

  return (
    <div
      ref={containerRef}
      id="phaser-container"
      className="w-full rounded-lg overflow-hidden"
      style={{ aspectRatio: '800/550' }}
    />
  );
}
