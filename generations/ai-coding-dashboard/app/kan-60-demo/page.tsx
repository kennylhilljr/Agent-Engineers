/**
 * KAN-60 Demo Page
 * Showcases dark theme, animations, and loading skeletons
 */

'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  fadeIn,
  slideUp,
  scaleIn,
  bounce,
  staggerContainer,
  staggerItem,
  hoverLift,
} from '@/lib/animations';
import { theme } from '@/lib/theme';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  TaskCardSkeleton,
  ProgressRingSkeleton,
  FileTreeSkeleton,
  TestResultsSkeleton,
} from '@/components/skeletons';
import { CheckCircle, Clock, Zap } from 'lucide-react';

export default function KAN60DemoPage() {
  const [showSkeletons, setShowSkeletons] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  const handleToggleSkeletons = () => {
    setShowSkeletons(!showSkeletons);
  };

  const handleShowSuccess = () => {
    setShowSuccess(true);
    setTimeout(() => setShowSuccess(false), 2000);
  };

  return (
    <div className="min-h-screen bg-background p-8 custom-scrollbar">
      <div className="max-w-7xl mx-auto space-y-12">
        {/* Header */}
        <motion.div
          variants={slideUp}
          initial="initial"
          animate="animate"
          className="text-center space-y-4"
        >
          <h1 className="text-4xl font-bold text-foreground">
            KAN-60: UI Polish Demo
          </h1>
          <p className="text-lg text-muted-foreground">
            Dark theme, animations, and loading skeletons
          </p>
        </motion.div>

        {/* Theme Colors */}
        <motion.section
          variants={fadeIn}
          initial="initial"
          animate="animate"
          className="space-y-4"
        >
          <h2 className="text-2xl font-semibold text-foreground">Color Palette</h2>
          <Card className="p-6">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {/* Status Colors */}
              {Object.entries(theme.status).map(([status, colors]) => (
                <div key={status} className="space-y-2">
                  <div
                    className="h-20 rounded-lg border-2"
                    style={{
                      backgroundColor: colors.bg,
                      borderColor: colors.border,
                    }}
                  />
                  <p className="text-sm font-medium text-foreground capitalize">
                    {status}
                  </p>
                  <Badge variant="outline" className="text-xs">
                    WCAG AA
                  </Badge>
                </div>
              ))}
            </div>
          </Card>
        </motion.section>

        {/* Animations Demo */}
        <motion.section
          variants={fadeIn}
          initial="initial"
          animate="animate"
          className="space-y-4"
        >
          <h2 className="text-2xl font-semibold text-foreground">Animations</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Fade In */}
            <motion.div variants={fadeIn} initial="initial" animate="animate">
              <Card className="p-6 text-center">
                <CardTitle className="mb-4">Fade In</CardTitle>
                <p className="text-sm text-muted-foreground">
                  200ms ease-out transition
                </p>
              </Card>
            </motion.div>

            {/* Slide Up */}
            <motion.div variants={slideUp} initial="initial" animate="animate">
              <Card className="p-6 text-center">
                <CardTitle className="mb-4">Slide Up</CardTitle>
                <p className="text-sm text-muted-foreground">
                  300ms with fade in
                </p>
              </Card>
            </motion.div>

            {/* Scale In */}
            <motion.div variants={scaleIn} initial="initial" animate="animate">
              <Card className="p-6 text-center">
                <CardTitle className="mb-4">Scale In</CardTitle>
                <p className="text-sm text-muted-foreground">
                  200ms from 95% to 100%
                </p>
              </Card>
            </motion.div>
          </div>

          {/* Bounce Animation */}
          <div className="flex justify-center">
            <Button onClick={handleShowSuccess} className="gap-2">
              <Zap className="w-4 h-4" />
              Trigger Success Animation
            </Button>
          </div>
          {showSuccess && (
            <motion.div
              variants={bounce}
              initial="initial"
              animate="animate"
              className="text-center"
            >
              <CheckCircle className="w-16 h-16 text-green-400 mx-auto" />
              <p className="text-lg text-green-400 font-semibold mt-2">
                Success!
              </p>
            </motion.div>
          )}
        </motion.section>

        {/* Interactive States */}
        <motion.section
          variants={fadeIn}
          initial="initial"
          animate="animate"
          className="space-y-4"
        >
          <h2 className="text-2xl font-semibold text-foreground">
            Interactive States
          </h2>
          <Card className="p-6">
            <div className="space-y-6">
              {/* Buttons */}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-foreground">Buttons</h3>
                <div className="flex flex-wrap gap-3">
                  <Button variant="default">Default</Button>
                  <Button variant="secondary">Secondary</Button>
                  <Button variant="outline">Outline</Button>
                  <Button variant="ghost">Ghost</Button>
                  <Button variant="destructive">Destructive</Button>
                  <Button disabled>Disabled</Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Hover for color change, click for scale effect, tab for focus ring
                </p>
              </div>

              {/* Hover Cards */}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-foreground">Hover Cards</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {[1, 2, 3].map((i) => (
                    <motion.div
                      key={i}
                      variants={hoverLift}
                      initial="rest"
                      whileHover="hover"
                      whileTap="tap"
                    >
                      <Card className="p-4 cursor-pointer hover:border-primary transition-all duration-200">
                        <div className="flex items-center gap-3">
                          <Clock className="w-5 h-5 text-primary" />
                          <div>
                            <p className="font-medium text-foreground">
                              Card {i}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              Hover to lift
                            </p>
                          </div>
                        </div>
                      </Card>
                    </motion.div>
                  ))}
                </div>
              </div>
            </div>
          </Card>
        </motion.section>

        {/* Loading Skeletons */}
        <motion.section
          variants={fadeIn}
          initial="initial"
          animate="animate"
          className="space-y-4"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold text-foreground">
              Loading Skeletons
            </h2>
            <Button
              onClick={handleToggleSkeletons}
              variant="outline"
              data-testid="toggle-skeletons"
            >
              {showSkeletons ? 'Hide Skeletons' : 'Show Skeletons'}
            </Button>
          </div>

          {showSkeletons && (
            <motion.div
              variants={staggerContainer}
              initial="initial"
              animate="animate"
              className="space-y-8"
            >
              {/* TaskCard Skeleton */}
              <motion.div variants={staggerItem}>
                <h3 className="text-lg font-semibold text-foreground mb-3">
                  TaskCard Skeleton
                </h3>
                <TaskCardSkeleton />
              </motion.div>

              {/* ProgressRing Skeleton */}
              <motion.div variants={staggerItem}>
                <h3 className="text-lg font-semibold text-foreground mb-3">
                  ProgressRing Skeleton
                </h3>
                <div className="flex justify-center">
                  <ProgressRingSkeleton size="medium" showMetrics={true} />
                </div>
              </motion.div>

              {/* FileTree Skeleton */}
              <motion.div variants={staggerItem}>
                <h3 className="text-lg font-semibold text-foreground mb-3">
                  FileTree Skeleton
                </h3>
                <Card className="p-6">
                  <FileTreeSkeleton depth={3} />
                </Card>
              </motion.div>

              {/* TestResults Skeleton */}
              <motion.div variants={staggerItem}>
                <h3 className="text-lg font-semibold text-foreground mb-3">
                  TestResults Skeleton
                </h3>
                <TestResultsSkeleton testCount={5} />
              </motion.div>
            </motion.div>
          )}
        </motion.section>

        {/* Typography */}
        <motion.section
          variants={fadeIn}
          initial="initial"
          animate="animate"
          className="space-y-4"
        >
          <h2 className="text-2xl font-semibold text-foreground">Typography</h2>
          <Card className="p-6 space-y-4">
            <div className="space-y-2">
              <h1 className="text-4xl font-bold text-foreground">
                Heading 1 - 36px
              </h1>
              <h2 className="text-2xl font-semibold text-foreground">
                Heading 2 - 24px
              </h2>
              <h3 className="text-xl font-semibold text-foreground">
                Heading 3 - 20px
              </h3>
              <p className="text-base text-foreground">
                Body text - 16px with 1.5 line height for readability
              </p>
              <p className="text-sm text-muted-foreground">
                Secondary text - 14px with muted color
              </p>
              <p className="text-xs text-muted-foreground">
                Caption text - 12px for labels and metadata
              </p>
            </div>
            <div className="pt-4 border-t border-border">
              <Badge variant="outline">All text meets WCAG AA contrast</Badge>
            </div>
          </Card>
        </motion.section>

        {/* Spacing Scale */}
        <motion.section
          variants={fadeIn}
          initial="initial"
          animate="animate"
          className="space-y-4"
        >
          <h2 className="text-2xl font-semibold text-foreground">
            Spacing Scale (4px Grid)
          </h2>
          <Card className="p-6">
            <div className="space-y-4">
              {Object.entries(theme.spacing).map(([name, value]) => (
                <div key={name} className="flex items-center gap-4">
                  <div className="w-24 text-sm font-mono text-muted-foreground">
                    {name}: {value}
                  </div>
                  <div
                    className="h-8 bg-primary rounded"
                    style={{ width: value }}
                  />
                </div>
              ))}
            </div>
          </Card>
        </motion.section>
      </div>
    </div>
  );
}
