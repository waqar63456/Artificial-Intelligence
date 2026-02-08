<!DOCTYPE html>
<html>
<head>
    <title>Generate AI Image</title>
</head>
<body>
    <h1>Generate an AI Image</h1>

    @if(session('error'))
        <p style="color:red;">{{ session('error') }}</p>
    @endif

    <form action="{{ route('generate.image') }}" method="POST">
        @csrf
        <label>Prompt:</label><br>
        <input type="text" name="prompt" value="A car driving in a misty forest" style="width: 300px;"><br><br>
        <button type="submit">Generate Image</button>


    </form>
<br>
<br><br><br>

    <img  src="{{ asset('images/images_123.jfif') }}" height="300">

</body>
</html>
