async function filterStream(originalStream: ReadableStream) {
    const reader = originalStream.getReader();
    const filteredStream = new ReadableStream({
        async start(controller) {
            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    controller.close();
                    break;
                }
                try {
                    const chunk = JSON.parse(value); 
                    if (chunk.type !== "step-finish") {
                        controller.enqueue(value);
                    }
                } catch (error) {
                    if (!(value.type==='step-finish')) {
                        controller.enqueue(value);
                    }
                }
            }
        }
    });

    return filteredStream;
}

export { filterStream };