<?php

namespace App\Listeners;

use App\Events\AnalyzeDocumentByAI;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Session;
use App\Events\ContinueWorkflow;
use OpenAI;
use Smalot\PdfParser\Parser;

class HandleAnalyzeDocumentByAI
{
    public function handle(AnalyzeDocumentByAI $event): void
    {
        Log::info("HandleAnalyzeDocumentByAI listener triggered.", [
            'workflow_id' => $event->workflow_id,
            'step' => $event->current_step,
            'task' => $event->task,
        ]);

        try {
            $filePath = storage_path('app/public/' . str_replace('storage/', '', $event->task['path']));
            $parser = new Parser();
            $pdf = $parser->parseFile($filePath);
            $text = $pdf->getText();

            if (!$text) {
                throw new \Exception("PDF seems empty or unreadable.");
            }

            // Clean the text for AI input
            $cleanText = mb_convert_encoding($text, 'UTF-8', 'UTF-8');
            $cleanText = preg_replace('/[^\PC\s]/u', '', $cleanText);
            if (!mb_check_encoding($cleanText, 'UTF-8')) {
                $cleanText = iconv('UTF-8', 'UTF-8//IGNORE', $cleanText);
            }

            $snippet = substr($cleanText, 0, 3000); // Limit input for token safety

            $client = OpenAI::client(env('OPENAI_API_KEY'));

            // Custom or default prompt
            $customPrompt = $event->task['custom_prompt'] ?? null;

            $defaultPrompt = "show same response as the chatgpt";
            $finalPrompt = $customPrompt ?: $defaultPrompt;

            // Send to OpenAI
            $response = $client->chat()->create([
                'model' => 'gpt-3.5-turbo',
                'messages' => [
                    ['role' => 'system', 'content' => 'You are an intelligent assistant. show same response as the chatgpt '],
                    ['role' => 'user', 'content' => <<<EOT
{$finalPrompt}

Here is the content:
---
{$snippet}
EOT
                    ],
                ],
            ]);

            $summary = $response->choices[0]->message->content ?? 'No response from AI.';

            // Save to session for display
            Session::put('document_summary', $summary);
            Session::put('custom_prompt', $customPrompt);

            // Trigger next step
            event(new ContinueWorkflow($event->workflow_id, $event->current_step + 1));
        } catch (\Exception $e) {
            Log::error("Failed to analyze document with OpenAI", [
                'error' => $e->getMessage(),
            ]);
            Session::put('document_summary', 'Error: ' . $e->getMessage());
        }
    }
}
