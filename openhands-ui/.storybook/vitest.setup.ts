import * as a11yAddonAnnotations from "@storybook/addon-a11y/preview";
import { beforeAll } from "vitest";
import { setProjectAnnotations } from "@storybook/react";
import * as previewAnnotations from "./preview";

const annotations = setProjectAnnotations([a11yAddonAnnotations, previewAnnotations]);

beforeAll(annotations.beforeAll);
