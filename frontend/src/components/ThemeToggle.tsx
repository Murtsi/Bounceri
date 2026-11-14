import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

type Theme = "light" | "dark";
const KEY = "bouncer-theme";

function initial(): Theme {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* yksityinen tila tms. → seurataan järjestelmää */
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Vaalea/tumma. Oletus = käyttöjärjestelmä; oma valinta muistetaan selaimessa. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initial);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.style.colorScheme = theme;
  }, [theme]);
  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <Button
      variant="outline"
      size="icon"
      aria-label={next === "dark" ? "Vaihda tummaan teemaan" : "Vaihda vaaleaan teemaan"}
      onClick={() => {
        setTheme(next);
        try {
          localStorage.setItem(KEY, next);
        } catch {
          /* ei tallennusta: valinta pätee tämän sivulatauksen ajan */
        }
      }}
    >
      {theme === "dark" ? <Sun /> : <Moon />}
    </Button>
  );
}
