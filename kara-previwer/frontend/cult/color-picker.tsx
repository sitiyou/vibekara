"use client"

import React, { useEffect, useRef, useState } from "react"
import { Check } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

const hexToHsl = (hex: string): [number, number, number] => {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  if (!result) return [0, 0, 0]

  const r = parseInt(result[1], 16) / 255
  const g = parseInt(result[2], 16) / 255
  const b = parseInt(result[3], 16) / 255

  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  let h = 0
  let s = 0
  const l = (max + min) / 2

  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    switch (max) {
      case r:
        h = (g - b) / d + (g < b ? 6 : 0)
        break
      case g:
        h = (b - r) / d + 2
        break
      case b:
        h = (r - g) / d + 4
        break
    }
    h /= 6
  }

  return [Math.round(h * 360), Math.round(s * 100), Math.round(l * 100)]
}

const normalizeColor = (color: string): string => {
  if (color.startsWith("#")) return color.toUpperCase()
  if (color.startsWith("hsl")) {
    const [h, s, l] = color.match(/\d+(\.\d+)?/g)?.map(Number) || [0, 0, 0]
    return `hsl(${Math.round(h)}, ${Math.round(s)}%, ${Math.round(l)}%)`
  }
  return color
}

const colorPresets = [
  "#FFFFFF",
  "#E6F4F1",
  "#FFD166",
  "#FF9F43",
  "#FF5C77",
  "#C084FC",
  "#60A5FA",
  "#2EA884",
  "#94A3B8",
  "#334155",
  "#18212B",
  "#0B0F14",
]

export function ColorPicker({
  color,
  onChange,
  id,
  extra,
}: {
  color: string
  onChange: (color: string) => void
  id?: string
  extra?: React.ReactNode
}) {
  const [hsl, setHsl] = useState<[number, number, number]>([0, 0, 0])
  const [colorInput, setColorInput] = useState(color)
  const [isOpen, setIsOpen] = useState(false)
  const dragging = useRef(false)

  useEffect(() => {
    handleColorChange(color, false)
  }, [color])

  const handleColorChange = (newColor: string, notify = true) => {
    const normalizedColor = normalizeColor(newColor)
    setColorInput(normalizedColor)

    let h, s, l
    if (normalizedColor.startsWith("#")) {
      ;[h, s, l] = hexToHsl(normalizedColor)
    } else {
      ;[h, s, l] = normalizedColor.match(/\d+(\.\d+)?/g)?.map(Number) || [
        0, 0, 0,
      ]
    }

    setHsl([h, s, l])
    if (notify) onChange(`hsl(${h.toFixed(1)}, ${s.toFixed(1)}%, ${l.toFixed(1)}%)`)
  }

  const handleHueChange = (hue: number) => {
    const next: [number, number, number] = [hue, hsl[1], hsl[2]]
    setHsl(next)
    handleColorChange(`hsl(${next[0]}, ${next[1]}%, ${next[2]}%)`)
  }

  const updatePlane = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const x = Math.max(0, Math.min(rect.width, event.clientX - rect.left))
    const y = Math.max(0, Math.min(rect.height, event.clientY - rect.top))
    const s = Math.round((x / rect.width) * 100)
    const l = Math.round(100 - (y / rect.height) * 100)
    const next: [number, number, number] = [hsl[0], s, l]
    setHsl(next)
    handleColorChange(`hsl(${next[0]}, ${next[1]}%, ${next[2]}%)`)
  }

  const handleColorInputChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const newColor = event.target.value
    setColorInput(newColor)
    if (/^#[0-9A-Fa-f]{6}$/.test(newColor)) {
      handleColorChange(newColor)
    }
  }

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          className="color-trigger"
          aria-label={colorInput}
        >
          <span
            className="color-swatch"
            style={{ backgroundColor: colorInput }}
          />
          <span className="color-hex">{colorInput}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="color-popover" align="start">
        <div className="color-popover-body">
          <div
            className="color-plane"
            style={{
              background: `
                linear-gradient(to top, rgba(0, 0, 0, 1), transparent),
                linear-gradient(to right, rgba(255, 255, 255, 1), rgba(255, 0, 0, 0)),
                hsl(${hsl[0]}, 100%, 50%)
              `,
            }}
            onPointerDown={(e) => {
              dragging.current = true
              e.currentTarget.setPointerCapture(e.pointerId)
              updatePlane(e)
            }}
            onPointerMove={(e) => {
              if (dragging.current) updatePlane(e)
            }}
            onPointerUp={() => {
              dragging.current = false
            }}
            onPointerCancel={() => {
              dragging.current = false
            }}
          >
            <div
              className="color-plane-thumb"
              style={{
                left: `${hsl[1]}%`,
                top: `${100 - hsl[2]}%`,
                backgroundColor: `hsl(${hsl[0]}, ${hsl[1]}%, ${hsl[2]}%)`,
              }}
            />
          </div>
          <input
            type="range"
            aria-label="色相"
            min="0"
            max="360"
            value={hsl[0]}
            onChange={(e) => handleHueChange(Number(e.target.value))}
            className="color-hue-slider"
          />
          <div className="color-input-row">
            <Label htmlFor="color-input" className="sr-only">
              颜色 Hex
            </Label>
            <span
              className="color-swatch color-swatch-lg"
              style={{ backgroundColor: colorInput }}
            />
            <Input
              id="color-input"
              type="text"
              value={colorInput}
              onChange={handleColorInputChange}
              className="color-hex-input"
              placeholder="#RRGGBB"
            />
          </div>
          {extra}
          <div className="color-presets">
            {colorPresets.map((preset) => (
              <button
                key={preset}
                type="button"
                className="color-preset"
                style={{ backgroundColor: preset }}
                aria-label={preset}
                onClick={() => handleColorChange(preset)}
              >
                {colorInput.toUpperCase() === preset && (
                  <Check className="color-preset-check" />
                )}
              </button>
            ))}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}

export default ColorPicker
