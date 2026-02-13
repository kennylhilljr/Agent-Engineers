"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { CheckCircle2, FileCode, PlayCircle } from "lucide-react";

interface DashboardHeaderProps {
  projectName: string;
  completionPercentage: number;
  tasksDone: number;
  tasksTotal: number;
  filesModified: number;
  testsPassed: number;
  testsTotal: number;
}

export function DashboardHeader({
  projectName,
  completionPercentage,
  tasksDone,
  tasksTotal,
  filesModified,
  testsPassed,
  testsTotal,
}: DashboardHeaderProps) {
  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex-1">
            <CardTitle className="text-3xl mb-2">{projectName}</CardTitle>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span>Overall Progress</span>
              <Badge variant="secondary">{completionPercentage}%</Badge>
            </div>
          </div>

          <div className="flex items-center justify-center w-24 h-24">
            <div className="relative w-full h-full">
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                <circle
                  className="text-muted stroke-current"
                  strokeWidth="8"
                  fill="transparent"
                  r="42"
                  cx="50"
                  cy="50"
                />
                <circle
                  className="text-primary stroke-current"
                  strokeWidth="8"
                  strokeLinecap="round"
                  fill="transparent"
                  r="42"
                  cx="50"
                  cy="50"
                  strokeDasharray={`${2 * Math.PI * 42}`}
                  strokeDashoffset={`${2 * Math.PI * 42 * (1 - completionPercentage / 100)}`}
                  style={{ transition: "stroke-dashoffset 0.5s ease" }}
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-xl font-bold">{completionPercentage}%</span>
              </div>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-center gap-3 p-4 rounded-lg bg-secondary/50">
            <div className="flex items-center justify-center w-10 h-10 rounded-full bg-primary/10">
              <CheckCircle2 className="w-5 h-5 text-primary" />
            </div>
            <div>
              <div className="text-2xl font-bold">{tasksDone}/{tasksTotal}</div>
              <div className="text-sm text-muted-foreground">Tasks Complete</div>
            </div>
          </div>

          <div className="flex items-center gap-3 p-4 rounded-lg bg-secondary/50">
            <div className="flex items-center justify-center w-10 h-10 rounded-full bg-primary/10">
              <FileCode className="w-5 h-5 text-primary" />
            </div>
            <div>
              <div className="text-2xl font-bold">{filesModified}</div>
              <div className="text-sm text-muted-foreground">Files Modified</div>
            </div>
          </div>

          <div className="flex items-center gap-3 p-4 rounded-lg bg-secondary/50">
            <div className="flex items-center justify-center w-10 h-10 rounded-full bg-primary/10">
              <PlayCircle className="w-5 h-5 text-primary" />
            </div>
            <div>
              <div className="text-2xl font-bold">{testsPassed}/{testsTotal}</div>
              <div className="text-sm text-muted-foreground">Tests Passed</div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
