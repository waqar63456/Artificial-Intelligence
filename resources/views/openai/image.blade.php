<!DOCTYPE html>
<html>
<head>
    <title>AI Image Result</title>
</head>
<body>
    <h2>Prompt: {{ $prompt }}</h2>
    <img src="{{ $imageUrl }}" alt="AI Generated Image" style="width: 500px;"><br><br>
    <a href="{{ route('image.form') }}">Try another prompt</a>
</body>
</html>
