import dotenv from "dotenv";
dotenv.config();

import { generateObject } from "ai";
import { testConfig } from "../../config/test-config";
import { z } from "zod";

interface Provider {
  name: string;
  activeModel: string;
  apiKey: string | undefined;
}

const provider: Provider = {
  name: "openai",
  activeModel: "gpt-4-turbo",
  apiKey: process.env.OPENAI_API_KEY,
}
describe("OPENAI Structured Outputs", () => {
  const { userId } = testConfig;
  let mem0: ReturnType<typeof testConfig.createTestClient>;
  jest.setTimeout(30000);

  beforeEach(() => {
    mem0 = testConfig.createTestClient(provider);
  });

  describe("openai Object Generation Tests", () => {
    // Test 1: Generate a car preference object
    it("should generate a car preference object with name and steps", async () => {
      const { object } = await generateObject({
        model: mem0(provider.activeModel, {
          user_id: userId,
        }),
        schema: z.object({
          car: z.object({
            name: z.string(),
            steps: z.array(z.string()),
          }),
        }),
        prompt: "Which car would I like?",
      });

      expect(object.car).toBeDefined();
      expect(typeof object.car.name).toBe("string");
      expect(Array.isArray(object.car.steps)).toBe(true);
      expect(object.car.steps.every((step) => typeof step === "string")).toBe(true);
    });

    // Test 2: Generate an array of car objects
    it("should generate an array of three car objects with name, class, and description", async () => {
      const { object } = await generateObject({
        model: mem0(provider.activeModel, {
          user_id: userId,
        }),
        output: "array",
        schema: z.object({
          name: z.string(),
          class: z.string().describe('Cars should be "SUV", "Sedan", or "Hatchback"'),
          description: z.string(),
        }),
        prompt: "Write name of three cars that I would like.",
      });

      expect(Array.isArray(object)).toBe(true);
      expect(object.length).toBe(3);
      object.forEach((car) => {
        expect(car).toHaveProperty("name");
        expect(typeof car.name).toBe("string");
        expect(car).toHaveProperty("class");
        expect(typeof car.class).toBe("string");
        expect(car).toHaveProperty("description");
        expect(typeof car.description).toBe("string");
      });
    });

    // Test 3: Generate an enum for movie genre classification
    it("should classify the genre of a movie plot", async () => {
      const { object } = await generateObject({
        model: mem0(provider.activeModel, {
          user_id: userId,
        }),
        output: "enum",
        enum: ["action", "comedy", "drama", "horror", "sci-fi"],
        prompt: 'Classify the genre of this movie plot: "A group of astronauts travel through a wormhole in search of a new habitable planet for humanity."',
      });

      expect(object).toBeDefined();
      expect(object).toBe("sci-fi");
    });

    // Test 4: Generate an object of car names without schema
    it("should generate an object with car names", async () => {
      const { object } = await generateObject({
        model: mem0(provider.activeModel, {
          user_id: userId,
        }),
        output: "no-schema",
        prompt: "Write name of 3 cars that I would like.",
      });

      const carObject = object as { cars: string[] };

      expect(carObject).toBeDefined();
      expect(typeof carObject.cars).toBe("object");
      expect(carObject.cars.length).toBe(3);
      expect(carObject.cars.every((car) => typeof car === "string")).toBe(true);
    });
  });
});
