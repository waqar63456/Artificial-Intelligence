<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use OpenAI;

class OpenAIImageController extends Controller
{
    public function generateImage(Request $request)
    {
        $prompt = $request->input('prompt', 'A realistic image of a red car driving through a misty forest');

        $client = OpenAI::client(env('OPENAI_API_KEY'));

        try {
            $response = $client->images()->create([
                'prompt' => $prompt,
                'n' => 1,
                'size' => '1024x1024',
            ]);

            $imageUrl = $response->data[0]->url;

            return view('openai.image', compact('imageUrl', 'prompt'));

        } catch (\Exception $e) {
            return back()->with('error', 'Image generation failed: ' . $e->getMessage());
        }
    }

    public function form()
    {
        return view('openai.form');
    }
}
