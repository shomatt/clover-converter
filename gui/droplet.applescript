-- Clover ⇄ MusicXML 変換 droplet.
-- Drop .clvz / .musicxml files or folders onto the app icon to convert them.
-- Wraps the frozen, Tk-free CLI binary embedded in this app bundle.

on _binPath()
	set appPath to POSIX path of (path to me)
	return appPath & "Contents/Resources/bin/clover-batch/clover-batch"
end _binPath

on _convert(theItems)
	set bin to _binPath()
	set args to ""
	repeat with f in theItems
		set args to args & " " & quoted form of (POSIX path of f)
	end repeat
	try
		set summary to do shell script quoted form of bin & args
		display notification summary with title "Clover変換" subtitle "変換完了"
	on error errMsg
		display notification errMsg with title "Clover変換" subtitle "エラー"
	end try
end _convert

-- Files/folders dropped onto the icon.
on open theItems
	_convert(theItems)
end open

-- Double-clicked with no files: let the user choose.
on run
	set chosen to choose file with prompt ¬
		"変換する .clvz / .musicxml ファイルを選択（複数可）" with multiple selections allowed
	_convert(chosen)
end run
