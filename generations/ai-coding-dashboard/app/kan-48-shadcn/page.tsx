"use client"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Toaster } from "@/components/ui/toaster"
import { useToast } from "@/hooks/use-toast"
import { useState } from "react"

export default function ShadcnDemoPage() {
  const { toast } = useToast()
  const [inputValue, setInputValue] = useState("")
  const [clickCount, setClickCount] = useState(0)

  const handleButtonClick = () => {
    setClickCount(prev => prev + 1)
    toast({
      title: "Button Clicked!",
      description: `You've clicked the button ${clickCount + 1} times.`,
    })
  }

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <div className="space-y-2">
          <h1 className="text-4xl font-bold tracking-tight">Shadcn/ui Demo - KAN-48</h1>
          <p className="text-muted-foreground">
            This page demonstrates all 7 installed shadcn/ui components in dark theme
          </p>
        </div>

        <Separator />

        {/* Buttons Section */}
        <Card>
          <CardHeader>
            <CardTitle>1. Button Component</CardTitle>
            <CardDescription>Various button variants and sizes</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-4">
              <Button variant="default" onClick={handleButtonClick}>Default</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="destructive">Destructive</Button>
              <Button variant="outline">Outline</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="link">Link</Button>
            </div>
            <div className="flex flex-wrap gap-4">
              <Button size="sm">Small</Button>
              <Button size="default">Default</Button>
              <Button size="lg">Large</Button>
            </div>
          </CardContent>
        </Card>

        <Separator />

        {/* Card Section */}
        <div className="space-y-4">
          <h2 className="text-2xl font-bold">2. Card Component</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Card Title</CardTitle>
                <CardDescription>Card description goes here</CardDescription>
              </CardHeader>
              <CardContent>
                <p>This is the card content area. Cards are great for organizing information.</p>
              </CardContent>
              <CardFooter>
                <Button variant="outline">Card Action</Button>
              </CardFooter>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Another Card</CardTitle>
                <CardDescription>With different content</CardDescription>
              </CardHeader>
              <CardContent>
                <p>Cards can contain any content and are fully customizable.</p>
              </CardContent>
            </Card>
          </div>
        </div>

        <Separator />

        {/* Input Section */}
        <Card>
          <CardHeader>
            <CardTitle>3. Input Component</CardTitle>
            <CardDescription>Form input with various types</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Text Input</label>
              <Input
                type="text"
                placeholder="Enter some text..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
              />
              {inputValue && <p className="text-sm text-muted-foreground">You typed: {inputValue}</p>}
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Email Input</label>
              <Input type="email" placeholder="your@email.com" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Password Input</label>
              <Input type="password" placeholder="Enter password" />
            </div>
          </CardContent>
        </Card>

        <Separator />

        {/* Dialog Section */}
        <Card>
          <CardHeader>
            <CardTitle>4. Dialog Component</CardTitle>
            <CardDescription>Modal dialog for user interactions</CardDescription>
          </CardHeader>
          <CardContent>
            <Dialog>
              <DialogTrigger asChild>
                <Button>Open Dialog</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Dialog Title</DialogTitle>
                  <DialogDescription>
                    This is a dialog component. It can be used for confirmations, forms, or any modal content.
                  </DialogDescription>
                </DialogHeader>
                <div className="py-4">
                  <Input placeholder="Example input in dialog" />
                </div>
                <DialogFooter>
                  <Button variant="outline">Cancel</Button>
                  <Button>Confirm</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </CardContent>
        </Card>

        <Separator />

        {/* Toast Section */}
        <Card>
          <CardHeader>
            <CardTitle>5. Toast Component</CardTitle>
            <CardDescription>Notification toast messages</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-4">
              <Button
                variant="default"
                onClick={() => toast({
                  title: "Success!",
                  description: "This is a success toast notification.",
                })}
              >
                Show Default Toast
              </Button>
              <Button
                variant="destructive"
                onClick={() => toast({
                  variant: "destructive",
                  title: "Error!",
                  description: "This is a destructive toast notification.",
                })}
              >
                Show Error Toast
              </Button>
            </div>
          </CardContent>
        </Card>

        <Separator />

        {/* Badge Section */}
        <Card>
          <CardHeader>
            <CardTitle>6. Badge Component</CardTitle>
            <CardDescription>Small labels and status indicators</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-4">
              <Badge variant="default">Default</Badge>
              <Badge variant="secondary">Secondary</Badge>
              <Badge variant="destructive">Destructive</Badge>
              <Badge variant="outline">Outline</Badge>
              <Badge>New</Badge>
              <Badge variant="secondary">Beta</Badge>
              <Badge variant="outline">v1.0.0</Badge>
            </div>
          </CardContent>
        </Card>

        <Separator />

        {/* Separator Section */}
        <Card>
          <CardHeader>
            <CardTitle>7. Separator Component</CardTitle>
            <CardDescription>Visual divider between content sections</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm">Horizontal Separator</p>
              <Separator className="my-4" />
              <p className="text-sm">Content below separator</p>
            </div>
            <div className="flex items-center space-x-4">
              <p className="text-sm">Vertical</p>
              <Separator orientation="vertical" className="h-10" />
              <p className="text-sm">Separator</p>
              <Separator orientation="vertical" className="h-10" />
              <p className="text-sm">Example</p>
            </div>
          </CardContent>
        </Card>

        {/* Click Counter */}
        <Card>
          <CardHeader>
            <CardTitle>Interactive Test</CardTitle>
            <CardDescription>Testing component functionality</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <p>Click count: <Badge>{clickCount}</Badge></p>
              <Button onClick={handleButtonClick}>
                Click Me to Test Toast & Counter
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <Toaster />
    </div>
  )
}
