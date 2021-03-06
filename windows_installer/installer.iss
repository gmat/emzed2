; Script generated by the Inno Setup Script Wizard.
; SEE THE DOCUMENTATION FOR DETAILS ON CREATING INNO SETUP SCRIPT FILES!

[Setup]
AppName=emzed

AppVerName=emzed 2

DefaultGroupName=emzed
DefaultDirName={pf}\emzed2
Uninstallable=Yes
ChangesAssociations=Yes

[Files]
Source: "create_bootstrap.bat"; DestDir: "{app}"
Source: "emzed_inspect.bat"; DestDir: "{app}"
Source: "install_emzed.bat"; DestDir: "{app}"
Source: "emzed_icon.ico"; DestDir: "{app}"
Source: "ez_setup.py"; DestDir: "{app}"

[UninstallDelete]
Type: filesandordirs; Name: "{%APPDATA}\emzed2"

[Icons]
Name: {group}\emzed2; Filename: {app}\run_or_bootstrap.bat; WorkingDir: {app}; IconFilename: {app}\emzed_icon.ico
Name: "{group}\uninstall emzed2"; Filename: "{uninstallexe}"

[Registry]
Root: HKCR; Subkey: ".table"; ValueType: string; ValueName: ""; ValueData: "emzed2"; Flags: uninsdeletevalue
Root: HKCR; Subkey: ".mzData"; ValueType: string; ValueName: ""; ValueData: "emzed2"; Flags: uninsdeletevalue
Root: HKCR; Subkey: ".mzML"; ValueType: string; ValueName: ""; ValueData: "emzed2"; Flags: uninsdeletevalue
Root: HKCR; Subkey: ".mzXML"; ValueType: string; ValueName: ""; ValueData: "emzed2"; Flags: uninsdeletevalue
Root: HKCR; Subkey: "emzed2\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """start.exe {app}\emzed_inspect.bat"" ""%1"""
                                       

[Run]
Filename: "{app}\create_bootstrap.bat"; Parameters: {code:GetPythonRootFolder|}; Description: "bootstrap emzed modules"; WorkingDir: {app}; 

[Code]
var InputFileWizardPage : TInputFileWizardPage;
procedure InitializeWizard;
var
  PythonExePath: String;
  PythonRootFolder: String;
  PythonExeName: String;
  
  ii : Integer;
  
begin                                                   
  
  if not RegQueryStringValue(HKEY_CLASSES_ROOT, 'Python.File\shell\open\command', '', PythonExePath) then
  begin
       RegQueryStringValue(HKEY_CLASSES_ROOT, 'Applications\python.exe\shell\open\command', '', PythonExePath)
  end;
  
  if Length(PythonExePath) > 0 then
  begin

     PythonRootFolder := ExtractFilePath(RemoveQuotes(PythonExePath));
     PythonExeName := ExtractFileName(RemoveQuotes(PythonExePath));
     ii := Pos('.exe" ', PythonExeName);
     Delete(PythonExeName, ii+4, Length(PythonExeName));
     PythonExePath := PythonRootFolder + PythonExeName;

  end;
  
  InputFileWizardPage := CreateInputFilePage(wpWelcome,
        'Select python.exe', 'Where is python.exe located?',
        'Select python.exe, then click Next.');

  InputFileWizardPage.Add('Location of python.exe:',
        'Executable files|*.exe',
        '.exe');

  InputFileWizardPage.Values[0] := '';
  if FileExists(PythonExePath) then;
  begin
    InputFileWizardPage.Values[0] := PythonExePath;
  end;
 


  
end;

function GetPythonRootFolder(ignore: String): String;
begin
  Result := InputFileWizardPage.Values[0];
end;

 

                                                                             


  



