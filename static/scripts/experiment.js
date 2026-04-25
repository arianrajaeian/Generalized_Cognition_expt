var my_node_id = null;

var p = 0.5;         
var s = null;         
var g = null;
var generalizedPositions = [];
var transmittedPositions = [];
var transmittedAnswers = {};
var task = null;
var toSolve = null;
var answers = [];
var activeIndex = 0;

var currentTimestep = 0;
var lifespan = 5;  // lifespan established at front end

var feedbackCorrectness = {};
var showingFeedback = false;

currentRound = 1
TotalRounds = 5 // will want this to equal the number of available networks





function arrowLabel(value) {
  switch (value) {
    case "UP": return "↑";
    case "DOWN": return "↓";
    case "LEFT": return "←";
    case "RIGHT": return "→";
    default: return "";
  }
}

function updateSubmitEnabled() {
  if (my_node_id !== null) {
    $("#submit").prop("disabled", false);
  } else {
    $("#submit").prop("disabled", true);
  }
  // check if all positions are filled
  var allFilled = true;
  for (var i = 0; i < toSolve; i++) {
    if (answers[i] === null) {
      allFilled = false;
      break;
    }
  }

  if (!allFilled) {
    $("#submit").prop("disabled", true);
  }
}

function pressContinue() {
  console.log("continue clicked"); //debugging
  feedbackCorrectness = {};
  showingFeedback = false;
  $("#submit").prop("disabled", false);
  if (currentTimestep < lifespan) {
    initializeTimestep();
  } else {
    finishedRound();
  }
}

function renderGrid() {
  renderParentGrid();
  highlightActiveTask();
  if (task === "A") {
    var $grid = $("#grid-A");
  } else {
    var $grid = $("#grid-B");
  }
  $grid.empty();
  $grid.css({
    display: "flex",
    flexDirection: "row", 
    gap: "8px"
  })

  for (var i = 0; i < toSolve; i++) {
    var $cell = $("<div></div>");
    $cell.addClass("gc-cell");
    $cell.attr("data-index", i);
    $cell.text(arrowLabel(answers[i]));

    var key = String(i);
    var borderStyle = "1px solid #999";
    var backgroundColor = "white";
    var textColor = "black";

    // generalized positions always blue
    if (generalizedPositions.includes(i)) {
    backgroundColor = "#d0ebff";
    }

    if (!showingFeedback && transmittedAnswers[key] !== undefined) {
    textColor = "#555";
    }

    // feedback overrides background
    if (showingFeedback && feedbackCorrectness[key] !== undefined) {
    if (feedbackCorrectness[key]) {
    borderStyle = "3px solid green";
    backgroundColor = "#d4edda";
    } else {
    borderStyle = "3px solid red";
    backgroundColor = "#f8d7da";
    }
    } else if (!showingFeedback && i === activeIndex) {
    borderStyle = "3px solid #000";
    }


    $cell.css({
      width: "60px",
      height: "60px",
      border: borderStyle,
      backgroundColor: backgroundColor,
      color: showingFeedback && Object.prototype.hasOwnProperty.call(feedbackCorrectness, key)
        ? (feedbackCorrectness[key] === true ? "green" : "red")
        : textColor,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontSize: "30px",
      cursor: showingFeedback ? "default" : "pointer",
      userSelect: "none"
    });

    (function(index){
      $cell.on("click", function() {
        if (showingFeedback) {return;}
        activeIndex = index;
        renderGrid();
        updateSubmitEnabled();
      });
    })(i);

    $grid.append($cell);
  }
}

function renderOtherGrid() {
if (task_other === "A") {
  var $container = $("#grid-A")
  var $parent_container = $("#parent-grid-A")
} else {
  var $container = $("#grid-B")
  var $parent_container = $("#parent-grid-B")
}

$container.empty();
$parent_container.empty();

// parent row
var $parentRow = $("<div></div>").css({
display: "flex",
gap: "8px"
});

for (var i = 0; i < toSolve_other; i++) {
var $cell = $("<div></div>");
var key = String(i);

var backgroundColor = generalizedPositions_other.includes(i)


var textColor = "#999";

$cell.text("?");

$cell.css({
width: "60px",
height: "60px",
border: "1px solid #999",
backgroundColor: backgroundColor,
display: "flex",
alignItems: "center",
justifyContent: "center",
fontSize: "30px",
color: textColor,
userSelect: "none",
cursor: "default"
});

$parentRow.append($cell);
}

$parent_container.append($parentRow);

// "your answers" row (STATIC, not editable)
var $row = $("<div></div>").css({
display: "flex",
gap: "8px",
marginTop: "5px"
});

for (var i = 0; i < toSolve_other; i++) {
var $cell = $("<div></div>");

var backgroundColor = generalizedPositions_other.includes(i)
? "#d0ebff"
: "white";

$cell.text(""); // always blank (not editable)

$cell.css({
width: "60px",
height: "60px",
border: "1px solid #999",
backgroundColor: backgroundColor,
display: "flex",
alignItems: "center",
justifyContent: "center",
fontSize: "30px",
cursor: "default"
});

$row.append($cell);
}

$container.append($row);
}

function highlightActiveTask() {
  if (task === "A") {
    $("#Task-A").css({
      border: "3px solic #000",
      backgroundColor: "#f4f6fb"
    })
    $("#Task-B").css({
      border: "3px solic #000",
      backgroundColor: "transparent"
    })
  } else {
    $("#Task-B").css({
      border: "3px solic #000",
      backgroundColor: "#f4f6fb"
    })
    $("#Task-A").css({
      border: "3px solic #000",
      backgroundColor: "transparent"
    })
  }
}

function renderParentGrid() {
  if (task === "A") {
    var $grid = $("#parent-grid-A");
  } else {
    var $grid = $("#parent-grid-B");
  }
  $grid.empty();
  $grid.css({
    display: "flex",
    flexDirection: "row", 
    gap: "8px"
  })
  
  for (var i = 0; i < toSolve; i++) {
  var $cell = $("<div></div>");
  $cell.addClass("gc-cell");
  
  var key = String(i);
  var parentValue = transmittedAnswers[key] !== undefined ? transmittedAnswers[key] : null;
  if (parentValue == null) {
    $cell.text("?");
  }
  else {
    $cell.text(arrowLabel(parentValue));
  }
  
  
  var backgroundColor = "white";
  var textColor = "#555"
  
  if (generalizedPositions.includes(i)) {
  backgroundColor = "#d0ebff";
  }

  if (parentValue == null) {
    textColor = "#999";
  }
  
  $cell.css({
  width: "60px",
  height: "60px",
  border: "1px solid #999",
  backgroundColor: backgroundColor,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: "30px",
  color: textColor,
  userSelect: "none"
  });
  
  $grid.append($cell);
  }
  }

  
function handleKeydown(e) {
  if (e.which === 13) {
    e.preventDefault();
    
    if (!$("#submit").prop("disabled")) {
    submitTimestep();
    } else if (showingFeedback) {
      pressContinue();
    }
    return;
    }


if (e.which === 8) {
  e.preventDefault();
  if (showingFeedback) {
    return;
  }
  
  var lastFilled = -1;
  for (var i = toSolve - 1; i >= 0; i--) {
  if (answers[i] !== null) {
  lastFilled = i;
  break;
  }
  }
  
  if (lastFilled >= 0) {
  answers[lastFilled] = null;
  activeIndex = lastFilled;
  renderGrid();
  updateSubmitEnabled();
  }
  
  return;
  }

  var map = { 37: "LEFT", 38: "UP", 39: "RIGHT", 40: "DOWN" };
  var val = map[e.which || e.keyCode];
  if (!val) {
    return;
  } else {
    if (showingFeedback) {
      return;
    } else {
    
    e.preventDefault();
    answers[activeIndex] = val;

    if (activeIndex < toSolve - 1) activeIndex += 1;

    renderGrid();
    updateSubmitEnabled();
    }
  }

}

function enableSubmitIfReady() {
  $("#submit").prop("disabled", my_node_id === null);
}


create_agent = function() {
  if (dallinger.storage.get("currentRound") === undefined) {
    currentRound = currentRound;
  } else{
    currentRound = dallinger.storage.get("currentRound");
  }
  $("#submit").prop("disabled", true);
  $("#continue").hide();

  my_node_id = null;

  $(document).off("keydown.gc").on("keydown.gc", handleKeydown); //key presses run handleKeydown()
  $("#submit").off("click.gc").on("click.gc", submitTimestep); // ensures submit runs submitTimestep()

  $("#continue").off("click.gc").on("click.gc", pressContinue); //continue button runs pressContinue()

  console.log("starting createAgent")  
  dallinger.createAgent() // create backend node
    .done(function(resp) {
      console.log("created agent, node id:", resp.node.id) // debugging
      my_node_id = resp.node.id;
      currentTimestep = 0;
      console.log("initializeTimestep, my_node_id:", my_node_id)
      initializeTimestep();
    })
    .fail(function(rejection) {
      if (rejection.status === 403) {
        console.log("403 rejection")
        dallinger.allowExit();
        dallinger.goToPage("questionnaire");
      } else {
        console.log("fail")
        dallinger.error(rejection);
      }
    });
};

function finishedRound() {
  currentRound += 1;
  dallinger.storage.set("currentRound", currentRound)
  
  if (currentRound <= TotalRounds) {
    dallinger.goToPage("between-rounds");
  } else {
    dallinger.allowExit();
    dallinger.goToPage("questionnaire");
  }
}

function initializeTimestep() {
  if (my_node_id === null) {
    console.log("initialize timestep called before node id was set")
    return;
  }
  currentTimestep += 1;
  console.log("continue worked")
   
  $("#submit").prop("disabled", true);
  
  dallinger.getInfos(my_node_id).done(function(resp) {
  var infos = resp.infos;  
  var timestepInfos = infos.filter(function(info) { 
  return info.type === "timestep_info"; // getting relevant info about how many to solve, generalized, etc.
  }); 
    
  var timestepInfo = timestepInfos[timestepInfos.length - 1];
  
  var payload = JSON.parse(timestepInfo.contents);
  
  console.log("Loaded timestep payload:", payload);
  
  if (!payload.task || payload.toSolve === undefined) {
  console.log("Invalid timestep payload:", payload);
  $("#submit").prop("disabled", true);
  return;
  }
  
  task = payload.task;
  toSolve = payload.toSolve;
  generalizedPositions = payload.generalized_positions || [];
  transmittedPositions = payload.transmitted_positions || [];
  transmittedAnswers = payload.transmitted_answers || {};
  
  answers = Array(toSolve).fill(null); // make array that will be filled with answers later
  
  activeIndex = 0;
  showingFeedback = false;
  feedbackCorrectness = {};

  var otherInfos = infos.filter(function(info) { 
  return info.type === "other_info";
  }); 
      
  var otherInfo = otherInfos[otherInfos.length - 1];
    
  var other = JSON.parse(otherInfo.contents);
    
    
  task_other = other.task;
  toSolve_other = other.toSolve;
  generalizedPositions_other = other.generalized_positions || [];
  transmittedPositions_other = other.transmitted_positions || [];
  transmittedAnswers_other = other.transmitted_answers || {};
  
  $("#continue").hide();
  $("#submit").show();
  $("#submit").prop("disabled", false); 
  
 $("#Main-header").html("Round " + currentRound + " of " + TotalRounds)
 $("#timestep").html("Timestep " + currentTimestep + " of " + lifespan)
  
  renderGrid();
  renderOtherGrid();
  updateSubmitEnabled();
  }).fail(function(err) {
  console.log("Failed to load timestep info:", err);
  $("#submit").prop("disabled", true);
  });
}


function submitTimestep() {
  for (var i = 0; i < toSolve; i++) {
    if (answers[i] === null) {
      return;
    }
  }
  
  if (my_node_id === null) return;

  var payload = {
    kind: "task_answer",
    timestep: currentTimestep,
    lifespan: lifespan,
    task: task,
    toSolve: toSolve,
    answers: answers,
    transmittedAnswers: transmittedAnswers,
    generalizedPositions: generalizedPositions
  };

  $("#submit").prop("disabled", true);

  dallinger.createInfo(my_node_id, {
    contents: JSON.stringify(payload),
    info_type: "TaskAnswer"
  })
  .done(function() {
    console.log("TaskAnswer saved successfully");

    dallinger.getInfos(my_node_id).done(function(resp) {
      var infos = resp.infos;
      
      var feedbackInfos = infos.filter(function(info) {
      return info.type === "feedback_info";
      });
      
      if (feedbackInfos.length === 0) {
      console.log("No feedback found");
      $("#submit").prop("disabled", false);
      return;
      }
      
      var feedbackInfo = feedbackInfos[feedbackInfos.length - 1];
      var feedback = JSON.parse(feedbackInfo.contents);
      
      feedbackCorrectness = feedback.feedback_correctness || {};
      generalizedPositions = feedback.generalized_positions || [];
      showingFeedback = true;
      
      $("#submit").hide();
      $("#continue").show();
      
      renderGrid();
      });
  })
  .fail(function(err) {
    console.log("SUBMIT FAILED:", err);
    $("#submit").prop("disabled", false);
  });
}

